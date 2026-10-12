import logging
from typing import Dict, Any, List

from backend.graph.state import ResearchState
from backend.agents.planner.agent import PlannerAgent
from backend.agents.literature.agent import LiteratureAgent
from backend.graph.routing import resolve_task_agent, RoutingError

logger = logging.getLogger(__name__)


def planner_node(state: ResearchState) -> Dict[str, Any]:
    """
    LangGraph node for executing the Research Planner Agent.
    Transforms the research_question in state into a structured research plan.
    """
    research_question = state.get("research_question", "")
    if not research_question:
        logger.error("planner_node called without research_question in state.")
        return {
            "status": "error",
            "errors": state.get("errors", []) + [{"node": "planner", "error": "Missing research_question"}]
        }

    logger.info(f"Executing planner_node for research question: {research_question[:50]}...")
    agent = PlannerAgent()
    structured_plan = agent.plan(research_question)

    plan_dict = structured_plan.model_dump()
    first_task = plan_dict["subtasks"][0]["task_id"] if plan_dict.get("subtasks") else ""

    return {
        "plan": plan_dict,
        "status": "plan_generated",
        "current_task": first_task,
    }


def task_router_node(state: ResearchState) -> Dict[str, Any]:
    """
    LangGraph node for deterministically routing the next executable task to its assigned specialized agent.
    
    Inspects plan subtasks and completed_tasks, finds the next executable subtask with satisfied
    dependencies, validates its assigned_agent using routing.py, and updates workflow state.
    """
    plan = state.get("plan")
    if not plan or not isinstance(plan, dict) or not plan.get("subtasks"):
        logger.error("task_router_node called without a valid plan in state.")
        existing_errors = state.get("errors", [])
        return {
            "status": "routing_error",
            "errors": existing_errors + [{"node": "task_router", "error": "Missing or empty research plan"}]
        }

    subtasks: List[Dict[str, Any]] = plan.get("subtasks", [])
    completed_tasks = set(state.get("completed_tasks", []))
    
    # Filter for subtasks that have not yet been completed
    uncompleted = [task for task in subtasks if task.get("task_id") not in completed_tasks]
    
    if not uncompleted:
        logger.info("All subtasks in research plan have been completed.")
        return {
            "status": "all_tasks_completed",
            "current_task": "",
            "next_agent": ""
        }

    # Find first subtask whose dependencies are all satisfied in completed_tasks
    executable_task: Dict[str, Any] = None
    for task in uncompleted:
        deps = task.get("dependencies", [])
        if all(dep in completed_tasks for dep in deps):
            executable_task = task
            break

    if not executable_task:
        logger.warning("No executable subtasks found; remaining subtasks have unfulfilled dependencies.")
        existing_errors = state.get("errors", [])
        return {
            "status": "routing_blocked",
            "errors": existing_errors + [{
                "node": "task_router",
                "error": "No executable tasks found; remaining tasks have unfulfilled dependencies"
            }]
        }

    # Resolve assigned agent via deterministic routing logic
    try:
        routed_info = resolve_task_agent(executable_task)
        task_id = executable_task.get("task_id")
        agent_name = routed_info["agent_name"]

        logger.info(f"task_router_node selected task '{task_id}' assigned to '{agent_name}'.")
        return {
            "current_task": task_id,
            "next_agent": agent_name,
            "status": "task_routed"
        }
    except RoutingError as err:
        logger.error(f"Routing error in task_router_node: {err}")
        existing_errors = state.get("errors", [])
        return {
            "status": "routing_error",
            "errors": existing_errors + [{
                "node": "task_router",
                "task_id": executable_task.get("task_id"),
                "error": str(err)
            }]
        }


def literature_node(state: ResearchState) -> Dict[str, Any]:
    """
    LangGraph node for executing the Literature Research Agent.
    Finds, retrieves, and synthesizes scholarly literature for the active subtask.
    """
    current_task_id = state.get("current_task", "")
    research_question = state.get("research_question", "")

    # Retrieve subtask details from research plan
    plan = state.get("plan", {})
    subtasks = plan.get("subtasks", []) if isinstance(plan, dict) else []
    task_info = next((t for t in subtasks if t.get("task_id") == current_task_id), {})
    task_desc = task_info.get("description", research_question)
    query = task_info.get("title", research_question)

    logger.info(f"literature_node executing for task '{current_task_id}': {query[:50]}")
    agent = LiteratureAgent()
    review_result = agent.run(query=query, task_description=task_desc, research_question=research_question)

    # Update completed tasks
    completed = list(state.get("completed_tasks", []))
    if current_task_id and current_task_id not in completed:
        completed.append(current_task_id)

    # Accumulate task results
    task_results = dict(state.get("task_results") or {})
    task_results[current_task_id] = review_result.model_dump()

    # Accumulate papers avoiding duplicates by title
    existing_papers = list(state.get("papers") or [])
    for paper in review_result.papers:
        p_dict = paper.model_dump()
        if not any(ep.get("title") == p_dict.get("title") for ep in existing_papers):
            existing_papers.append(p_dict)

    return {
        "papers": existing_papers,
        "task_results": task_results,
        "completed_tasks": completed,
        "status": "task_completed"
    }


def task_executor_node(state: ResearchState) -> Dict[str, Any]:
    """
    Executor node: dispatches to specialized agent if available,
    or completes as stub for agents under development.
    """
    next_agent = state.get("next_agent", "")
    if next_agent == "literature_agent":
        return literature_node(state)

    current_task = state.get("current_task", "")
    completed = list(state.get("completed_tasks", []))
    if current_task and current_task not in completed:
        logger.info(f"task_executor_node marking '{current_task}' as completed (stub for {next_agent}).")
        completed.append(current_task)
    return {"completed_tasks": completed, "status": "task_completed"}

