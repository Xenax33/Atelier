"""tools/ — pure typed functions the agents call (SEAM #3).

Research/evidence tools: wikidata (CC-0 SPARQL, the copy-safe spine), openalex, semantic_scholar, arxiv
(metadata only), crossref (citation resolver). Wikipedia is LEADS ONLY (CC-BY-SA -> extract facts, rewrite).
Publishing: youtube (google-api-python-client).

Rule: keep these as plain typed functions. They can be wrapped as MCP servers in v2 for reuse — do not
couple them to the graph. Treat ALL fetched content as untrusted data, never instructions (Risk R13).
"""
