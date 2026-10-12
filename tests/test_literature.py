import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.agents.literature.agent import LiteratureAgent
from backend.agents.literature.schema import PaperMetadata, LiteratureReviewResult
from backend.graph.nodes import literature_node
from backend.graph.workflow import research_workflow
from backend.graph.state import ResearchState


class TestLiteratureAgent(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.sample_query = "Compare Transformer-based models with traditional ML models for sentiment classification."

    def test_paper_metadata_schema(self):
        """Verify PaperMetadata model structure and defaults."""
        paper = PaperMetadata(
            paper_id="test_doi_123",
            title="Attention Is All You Need",
            authors=["Vaswani et al."],
            abstract="We propose the Transformer.",
            year=2017,
            url="https://arxiv.org/abs/1706.03762",
            source="arxiv",
            citation_count=100000
        )
        self.assertEqual(paper.paper_id, "test_doi_123")
        self.assertEqual(paper.source, "arxiv")
        self.assertEqual(paper.year, 2017)

    def test_literature_agent_fallback_mode(self):
        """Verify agent returns structured baseline papers when external network calls fail."""
        agent = LiteratureAgent()
        with patch.object(agent, "search_openalex", return_value=[]), \
             patch.object(agent, "search_arxiv", return_value=[]), \
             patch.object(agent, "search_semantic_scholar", return_value=[]):
            papers = agent.search(self.sample_query, limit=3)
            self.assertTrue(len(papers) >= 1)
            self.assertEqual(papers[0].source, "baseline")
            self.assertTrue(len(papers[0].title) > 0)

    def test_literature_agent_run(self):
        """Verify LiteratureAgent.run executes and returns LiteratureReviewResult."""
        agent = LiteratureAgent()
        result = agent.run(
            query="Transformer models sentiment analysis",
            research_question=self.sample_query
        )

        self.assertIsInstance(result, LiteratureReviewResult)
        self.assertTrue(len(result.papers) > 0)
        self.assertTrue(len(result.summary) > 0)
        self.assertEqual(result.total_found, len(result.papers))

    def test_literature_node_execution(self):
        """Verify literature_node updates state with papers and task results."""
        state: ResearchState = {
            "research_id": "test_lit_run",
            "research_question": self.sample_query,
            "current_task": "task_1",
            "completed_tasks": [],
            "papers": [],
            "task_results": {},
            "plan": {
                "subtasks": [
                    {
                        "task_id": "task_1",
                        "title": "Literature Review & Baseline Identification",
                        "description": "Search literature for models.",
                        "category": "literature",
                        "assigned_agent": "literature_agent"
                    }
                ]
            }
        }

        output = literature_node(state)

        self.assertEqual(output.get("status"), "task_completed")
        self.assertIn("task_1", output.get("completed_tasks", []))
        self.assertTrue(len(output.get("papers", [])) > 0)
        self.assertIn("task_1", output.get("task_results", {}))

    def test_workflow_end_to_end_with_literature_agent(self):
        """Verify full LangGraph workflow runs literature_agent and populates papers in final state."""
        initial_state: ResearchState = {
            "research_id": "wf_test_lit_001",
            "research_question": self.sample_query,
            "completed_tasks": [],
            "papers": [],
            "task_results": {},
            "status": "pending"
        }

        final_state = research_workflow.invoke(initial_state)

        self.assertEqual(final_state.get("status"), "all_tasks_completed")
        self.assertTrue(len(final_state.get("papers", [])) > 0, "Papers should be populated by literature_agent")
        self.assertIn("task_1", final_state.get("task_results", {}), "task_1 result should be in task_results")
        self.assertIn("task_1", final_state.get("completed_tasks", []))

    def test_api_post_research_plan_includes_papers(self):
        """Verify POST /research/plan API endpoint response contains papers from literature review."""
        response = self.client.post(
            "/research/plan",
            json={"research_question": self.sample_query}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "all_tasks_completed")
        self.assertIn("papers", data)
        self.assertTrue(len(data["papers"]) > 0, "API response must include papers found by literature_agent")
        first_paper = data["papers"][0]
        self.assertIn("title", first_paper)
        self.assertIn("source", first_paper)


if __name__ == "__main__":
    unittest.main()
