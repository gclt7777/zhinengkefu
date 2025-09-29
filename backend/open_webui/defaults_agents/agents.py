"""Seed default multi-agent pipelines for Open WebUI."""

from __future__ import annotations

from textwrap import dedent
from typing import Final


MULTI_AGENT_PIPELINE_ID: Final[str] = "tri_role_support"
MULTI_AGENT_PIPELINE_NAME: Final[str] = "Tri-Role Support Agents"
MULTI_AGENT_PIPELINE_DESCRIPTION: Final[str] = (
    "预置的客户/供应商/中间商三角色客服智能体，演示如何在单个管线内编排多智能体。"
)


MULTI_AGENT_PIPELINE_CONTENT: Final[str] = dedent(
    '''
    """
    name: Tri-Role Support Agents
    description: Multi-agent customer support pipeline with role-aware RAG context.
    """

    from __future__ import annotations

    from dataclasses import dataclass
    from typing import Any, Dict, Iterable, List, Optional

    from pydantic import BaseModel, Field

    from open_webui.retrieval.utils import (
        query_collection,
        query_collection_with_hybrid_search,
    )
    from open_webui.utils.chat import generate_chat_completion
    from open_webui.utils.misc import add_or_update_system_message, get_last_user_message


    @dataclass
    class _ProxyUser:
        data: Dict[str, Any]

        @property
        def id(self) -> str:
            return self.data.get("id", "system")

        @property
        def role(self) -> str:
            return self.data.get("role", "admin")

        @property
        def email(self) -> str:
            return self.data.get("email", "")

        @property
        def name(self) -> str:
            return self.data.get("name", "")

        def model_dump(self) -> Dict[str, Any]:
            return self.data


    class Pipe:
        name = "Tri-Role Support"

        class Valves(BaseModel):
            base_model: str = "gpt-4o-mini"
            customer_system_prompt: str = Field(
                default="你是一位友善的客户支持代表，请用简洁明确的语言帮助终端客户，必要时给出下一步建议。"
            )
            supplier_system_prompt: str = Field(
                default="你是供应商运营支持专家，请聚焦合同、发货、结算等供应链问题，语言保持专业但易于理解。"
            )
            broker_system_prompt: str = Field(
                default="你是中间商协调专员，需要在客户与供应商之间平衡需求，强调进度、风险与下一步行动。"
            )
            customer_collections: List[str] = Field(default_factory=list)
            supplier_collections: List[str] = Field(default_factory=list)
            broker_collections: List[str] = Field(default_factory=list)
            rag_top_k: Optional[int] = None
            relevance_threshold: Optional[float] = None
            hybrid_search_override: Optional[bool] = None

        def __init__(self) -> None:
            self.type = "manifold"
            self.valves = self.Valves()
            self.pipes = [
                {"id": "customer", "name": " · 客户客服"},
                {"id": "supplier", "name": " · 供应商客服"},
                {"id": "broker", "name": " · 中间商客服"},
            ]

        async def pipe(
            self,
            body: dict,
            __request__=None,
            __user__: Optional[dict] = None,
        ):
            if __request__ is None:
                raise ValueError("Request context is required for the pipeline to run")

            role = self._resolve_role(body.get("model", ""))
            proxy_user = _ProxyUser(__user__ or {})

            config = getattr(__request__.app.state, "config")
            embedding_function = getattr(__request__.app.state, "EMBEDDING_FUNCTION", None)
            reranking_function = getattr(__request__.app.state, "RERANKING_FUNCTION", None)

            last_user_message = get_last_user_message(body.get("messages", []))
            context_blocks: List[str] = []

            if last_user_message and embedding_function and not getattr(
                config, "BYPASS_EMBEDDING_AND_RETRIEVAL", False
            ):
            context_blocks = self._run_rag(
                role=role,
                query=last_user_message,
                embedding_function=embedding_function,
                reranking_function=reranking_function,
                config=config,
                proxy_user=proxy_user,
            )

            system_prompt = self._build_system_prompt(role, context_blocks)
            messages = [dict(m) for m in body.get("messages", [])]
            messages = add_or_update_system_message(system_prompt, messages)

            payload = {**body, "messages": messages, "model": self.valves.base_model}
            return await generate_chat_completion(
                __request__,
                form_data=payload,
                user=proxy_user,
                bypass_filter=True,
            )

        def _resolve_role(self, model: str) -> str:
            if model and "." in model:
                return model.split(".", 1)[1]
            return "customer"

        def _build_system_prompt(self, role: str, context_blocks: Iterable[str]) -> str:
            prompt_lookup = {
                "customer": self.valves.customer_system_prompt,
                "supplier": self.valves.supplier_system_prompt,
                "broker": self.valves.broker_system_prompt,
            }
            base_prompt = prompt_lookup.get(role, self.valves.customer_system_prompt)
            context_text = "\n\n".join(block for block in context_blocks if block)
            if context_text:
                return (
                    f"{base_prompt}\n\n可用参考资料：\n{context_text}\n\n"
                    "若参考资料不足，请主动说明信息缺失。"
                )
            return base_prompt

        def _run_rag(
            self,
            role: str,
            query: str,
            embedding_function,
            reranking_function,
            config,
            proxy_user,
        ) -> List[str]:
            collection_lookup = {
                "customer": self.valves.customer_collections,
                "supplier": self.valves.supplier_collections,
                "broker": self.valves.broker_collections,
            }
            collections = [
                name for name in collection_lookup.get(role, []) if isinstance(name, str) and name.strip()
            ]
            if not collections:
                return []

            top_k = self.valves.rag_top_k or getattr(config, "TOP_K", 4)
            relevance_threshold = self.valves.relevance_threshold
            if relevance_threshold is None:
                relevance_threshold = getattr(config, "RELEVANCE_THRESHOLD", 0.0)

            hybrid_search = self.valves.hybrid_search_override
            if hybrid_search is None:
                hybrid_search = getattr(config, "ENABLE_RAG_HYBRID_SEARCH", False)

            if hybrid_search and reranking_function:
                rerank = (
                    (lambda sentences: reranking_function(sentences, user=proxy_user))
                    if callable(reranking_function)
                    else None
                )
                result = query_collection_with_hybrid_search(
                    collections,
                    [query],
                    lambda queries, prefix=None: embedding_function(
                        queries, prefix=prefix, user=proxy_user
                    ),
                    top_k,
                    rerank,
                    getattr(config, "TOP_K_RERANKER", top_k),
                    getattr(config, "RELEVANCE_THRESHOLD", 0.0),
                    getattr(config, "HYBRID_BM25_WEIGHT", 0.5),
                )
            else:
                result = query_collection(
                    collections,
                    [query],
                    lambda queries, prefix=None: embedding_function(
                        queries, prefix=prefix, user=proxy_user
                    ),
                    top_k,
                )

            return self._format_context_blocks(result, relevance_threshold)

        def _format_context_blocks(self, result: Optional[dict], threshold: float) -> List[str]:
            if not result:
                return []

            documents = result.get("documents", [])
            metadatas = result.get("metadatas", [])
            distances = result.get("distances", [])

            context_blocks: List[str] = []
            for docs, metas, scores in zip(documents, metadatas, distances):
                for doc, meta, score in zip(docs, metas, scores):
                    if score is not None and score < threshold:
                        continue
                    source = (
                        meta.get("source")
                        or meta.get("title")
                        or meta.get("name")
                        or meta.get("file_id")
                        or "资料片段"
                    )
                    snippet = doc.strip()
                    if snippet:
                        context_blocks.append(f"[{source}]\n{snippet}")
            return context_blocks
    '''
)


_DEFAULT_AGENTS_SEEDED: bool = False


def ensure_default_agents() -> None:
    """Ensure that the built-in multi-agent pipeline exists."""

    global _DEFAULT_AGENTS_SEEDED
    if _DEFAULT_AGENTS_SEEDED:
        return

    from open_webui.models.functions import FunctionForm, FunctionMeta, Functions

    try:
        existing = Functions.get_function_by_id(MULTI_AGENT_PIPELINE_ID)
        if existing is not None:
            if not getattr(existing, "is_active", True) or not getattr(
                existing, "is_global", True
            ):
                Functions.update_function_by_id(
                    MULTI_AGENT_PIPELINE_ID,
                    {"is_active": True, "is_global": True},
                )
            _DEFAULT_AGENTS_SEEDED = True
            return

        form = FunctionForm(
            id=MULTI_AGENT_PIPELINE_ID,
            name=MULTI_AGENT_PIPELINE_NAME,
            content=MULTI_AGENT_PIPELINE_CONTENT,
            meta=FunctionMeta(description=MULTI_AGENT_PIPELINE_DESCRIPTION),
        )
        created = Functions.insert_new_function("system", "pipe", form)
        if created is not None:
            Functions.update_function_by_id(
                MULTI_AGENT_PIPELINE_ID,
                {"is_active": True, "is_global": True},
            )
        _DEFAULT_AGENTS_SEEDED = True
    except Exception:
        # Default seeding should never break the application startup
        return
