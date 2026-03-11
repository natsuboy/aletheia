"""Wiki 专用提示词模板"""

WIKI_PAGE_PROMPT = """\
You are a technical documentation writer. Generate a comprehensive wiki page in Markdown \
based on the following code entity context, source code, and graph relationships.

## Entity Context
{entity_context}

## Related Code Snippets
{code_snippets}

## Graph Relationships
{graph_relations}

## Instructions
1. Write a clear, well-structured Markdown document for this code entity.
2. Include: purpose, key responsibilities, usage patterns, and important relationships.
3. Use code blocks for inline examples when relevant.
4. Reference related entities by name when describing relationships.
5. Keep the tone technical but accessible.
6. If Mermaid diagrams would help illustrate relationships, include them in ```mermaid blocks.

Generate the wiki page content now:
"""

WIKI_OVERVIEW_PROMPT = """\
You are a technical documentation writer. Generate a project overview page in Markdown \
based on the following graph statistics and key entities.

## Project Statistics
{graph_stats}

## Key Entities
{key_entities}

## Community Structure
{community_summary}

## Instructions
1. Write a high-level project overview suitable as the landing page of a wiki.
2. Summarize the architecture, main modules, and how they interact.
3. Mention key entry points and core abstractions.
4. Keep it concise but informative.

Generate the project overview now:
"""

WIKI_STRUCTURE_REVIEW_PROMPT = """\
You are a documentation architect. Review the following candidate wiki structure \
and improve it by renaming sections, merging small communities, and splitting large ones.

## Candidate Structure
{candidate_structure}

## Node Names by Section
{node_names_by_section}

## Instructions
1. Rename sections to be human-readable and descriptive (e.g., "community_3" -> "Authentication & Authorization").
2. Merge sections with fewer than 3 nodes into related larger sections.
3. Split sections with more than 20 nodes into logical sub-sections.
4. Reorder sections so that foundational/core modules come first.
5. Suggest a short description for each section.

Respond in JSON format:
{{
  "sections": [
    {{
      "id": "section_id",
      "title": "Human Readable Title",
      "description": "Brief description",
      "merge_into": null,
      "split_into": null,
      "order": 1
    }}
  ]
}}
"""

WIKI_DIAGRAM_PROMPT = """\
Generate a Mermaid diagram from the following entity relationships.

## Entities
{entities}

## Relationships
{relationships}

## Instructions
1. Use the most appropriate Mermaid diagram type (flowchart, classDiagram, sequenceDiagram).
2. Keep the diagram focused and readable (max ~15 nodes).
3. Use short but descriptive labels.
4. Return ONLY the Mermaid code block content (no surrounding ```mermaid markers).

Generate the Mermaid diagram now:
"""
