"""RAG 代理工具集合"""
import json
from typing import Dict, Any, List
from loguru import logger

from src.graph.client import GraphClient
from src.graph.view_service import GraphViewService


class GraphAgentTools:
    """提供给大模型 (LLM) 调用的图谱分析工具"""

    def __init__(self, graph_client: GraphClient):
        self.graph_client = graph_client
        self.view_service = GraphViewService(graph_client)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """返回 OpenAI 格式的工具定义"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_codebase_overview",
                    "description": "获取项目代码库的结构总览，包括核心模块、顶层文件夹和它们之间的依赖关系。在用户询问架构、项目结构时使用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "description": "项目名称"
                            }
                        },
                        "required": ["project"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_blast_radius",
                    "description": "分析一个类、函数或文件的爆炸半径 / 影响面。当用户询问修改某段代码会有什么风险、谁依赖了它时调用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "description": "项目名称"
                            },
                            "target_name": {
                                "type": "string",
                                "description": "目标实体名称 (例如函数名或类名)"
                            },
                            "direction": {
                                "type": "string",
                                "enum": ["upstream", "downstream", "both"],
                                "description": "影响方向。upstream (谁依赖它，即修改它的影响面)，downstream (它依赖谁)。默认为 upstream。"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "分析的最大跳数深度 (1-5)。默认为 3。"
                            }
                        },
                        "required": ["project", "target_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "trace_function_execution",
                    "description": "追踪某个入口点 (如 API Handler、Controller 或 main 函数) 的后端执行执行链路。了解完整的代码调用流向。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {
                                "type": "string",
                                "description": "项目名称"
                            },
                            "entry_name": {
                                "type": "string",
                                "description": "入口点实体名称 (例如 handler 函数)"
                            },
                            "max_steps": {
                                "type": "integer",
                                "description": "向下追踪追踪的最大步数 (1-10)。默认为 5。"
                            }
                        },
                        "required": ["project", "entry_name"]
                    }
                }
            }
        ]

    def _find_entity_id(self, project: str, name: str) -> str:
        """根据名称模糊查找实体 ID"""
        query = """
        MATCH (p:Project {id: $project_id})-[:CONTAINS|DEFINES*]->(n)
        WHERE NOT n:Project AND toLower(n.name) CONTAINS toLower($name)
        RETURN n.id AS id, n.name AS exact_name
        ORDER BY size(n.name) ASC
        LIMIT 1
        """
        rows = self.graph_client.execute_query(
            query, {"project_id": f"project:{project}", "name": name}
        )
        if not rows:
            raise ValueError(f"Could not find entity matching '{name}' in project {project}")
        return rows[0]["id"]

    def execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """执行工具调用，返回结果字符串 (通常为 JSON)"""
        name = tool_call.get("name")
        args_str = tool_call.get("arguments", "{}")
        try:
            args = json.loads(args_str)
        except Exception:
            args = {}

        logger.info(f"LLM called tool: {name} with args: {args}")

        try:
            if name == "get_codebase_overview":
                result = self.view_service.build_overview_view(
                    project=args["project"],
                    node_budget=100,  # 限制数量避免大模型 Token 溢出
                    edge_budget=200
                )
                return json.dumps({
                    "task": "overview",
                    "nodes": [ {"id": n["id"], "name": n["name"], "label": n["label"]} for n in result.get("nodes", []) ],
                    "summary": "这是代码库的顶级模块结构。"
                }, ensure_ascii=False)

            elif name == "analyze_blast_radius":
                target_id = self._find_entity_id(args["project"], args["target_name"])
                result = self.view_service.build_impact_view(
                    project=args["project"],
                    target_id=target_id,
                    direction=args.get("direction", "upstream"),
                    max_depth=args.get("max_depth", 3),
                    node_budget=100,
                    edge_budget=200
                )
                # 精简返回结果给 LLM
                impact = result.get("impact", {})
                return json.dumps({
                    "task": "blast_radius",
                    "target_name": args["target_name"],
                    "risk_level": impact.get("risk"),
                    "total_affected": impact.get("total_affected"),
                    "details": [ {"id": n["id"], "name": n["name"], "label": n["label"]} for n in result.get("nodes", []) ]
                }, ensure_ascii=False)

            elif name == "trace_function_execution":
                entry_id = self._find_entity_id(args["project"], args["entry_name"])
                result = self.view_service.build_entry_flow_view(
                    project=args["project"],
                    entry_id=entry_id,
                    max_steps=args.get("max_steps", 5),
                    node_budget=100,
                    edge_budget=200
                )
                nodes = result.get("nodes", [])
                return json.dumps({
                    "task": "execution_trace",
                    "entry_name": args["entry_name"],
                    "execution_path": [ {"step": i, "name": n["name"], "label": n["label"]} for i, n in enumerate(nodes) ]
                }, ensure_ascii=False)

            else:
                return f"Error: Unknown tool {name}"

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return f"Error executing {name}: {str(e)}"
