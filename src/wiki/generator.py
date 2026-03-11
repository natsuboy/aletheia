"""Wiki 生成器 — 编排结构分析 + 内容生成 + 缓存"""

import asyncio
from loguru import logger

from src.wiki.models import WikiStructure
from src.wiki.structure_analyzer import WikiStructureAnalyzer
from src.wiki.content_generator import WikiContentGenerator
from src.wiki.cache import WikiCache


class WikiGenerator:
    """Wiki 生成编排器，支持增量生成"""

    def __init__(
        self,
        structure_analyzer: WikiStructureAnalyzer,
        content_generator: WikiContentGenerator,
        cache: WikiCache,
    ):
        self.structure_analyzer = structure_analyzer
        self.content_generator = content_generator
        self.cache = cache

    async def generate(self, project_id: str) -> WikiStructure:
        """完整生成流程：结构分析 -> 逐页内容生成 -> 缓存"""
        logger.info(f"Starting wiki generation for project {project_id}")

        # Step a: 生成骨架
        wiki = await self.structure_analyzer.analyze_structure()

        # Step b: 逐页生成内容
        for page_id, page in wiki.pages.items():
            try:
                wiki.pages[page_id] = await self.content_generator.generate_page_content(
                    page, project_id
                )
            except Exception as e:
                logger.error(f"Failed to generate page {page_id}: {e}")
                page.content = f"(Generation failed: {e})"

        # Step c: 缓存
        await self.cache.save(project_id, wiki)

        logger.info(
            f"Wiki generation complete: {len(wiki.pages)} pages, "
            f"{len(wiki.sections)} sections"
        )
        return wiki
