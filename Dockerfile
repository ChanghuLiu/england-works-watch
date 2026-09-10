FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY data ./data
COPY tests ./tests
COPY scripts ./scripts
RUN pip install --no-cache-dir '.[x402,test]' \
 && pytest -q \
 && PYTHONPATH=src python scripts/acceptance_report.py \
 && PYTHONPATH=src python scripts/selection_benchmark.py \
 && PYTHONPATH=src python scripts/audit_sources.py
# Runtime-import and real MCP release gates. The first smoke proves the ordinary
# decision path over Streamable HTTP; the second starts a separate paid-mode
# server and proves an unpaid request terminates at x402 without decision leakage.
RUN ln -s /app/data /usr/local/lib/python3.12/data \
 && python -c "from england_works_watch.policy import source_status; s=source_status(); assert s['coverage_complete']; print('installed-runtime-import=PASS', s['rule_pack_version'])" \
 && python scripts/mcp_transport_smoke.py \
 && python scripts/x402_unpaid_smoke.py
RUN useradd --uid 10001 --create-home appuser && mkdir -p /data && chown -R appuser:appuser /data /app
USER appuser
ENV HOST=0.0.0.0 PORT=8000 EWW_RUNTIME_DIR=/data
CMD ["england-works-watch", "--http"]
