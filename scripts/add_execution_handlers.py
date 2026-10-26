# scripts/add_execution_handlers.py
from pathlib import Path

app_js_path = Path("ui/static/app.js")
text = app_js_path.read_text(encoding="utf-8")

# 1. Add window.setAgentExecutionMode & window.setAgentConcurrency
funcs = """  window.setAgentExecutionMode = async function (mode) {
    try {
      const currParallel = (state.appState && state.appState.execution && state.appState.execution.max_parallel_agents) || 2;
      const targetParallel = mode === "mono" ? 1 : (currParallel > 1 ? currParallel : 2);
      const res = await apiPost("/api/execution/mode", {
        mode: mode,
        max_parallel_agents: targetParallel,
      });
      if (res && res.execution && state.appState) {
        state.appState.execution = res.execution;
        renderInspector();
      } else {
        await refreshFullState();
      }
    } catch (err) {
      showStatusBanner(`Erreur changement de mode : ${err.message}`, "error");
    }
  };

  window.setAgentConcurrency = async function (count) {
    try {
      const num = parseInt(count, 10);
      if (isNaN(num) || num < 1) return;
      const res = await apiPost("/api/execution/config", {
        max_parallel_agents: num,
      });
      if (res && res.execution && state.appState) {
        state.appState.execution = res.execution;
        renderInspector();
      } else {
        await refreshFullState();
      }
    } catch (err) {
      showStatusBanner(`Erreur réglage agents simultanés : ${err.message}`, "error");
    }
  };
"""

if "window.setAgentExecutionMode" not in text:
    marker = "function renderInspector() {"
    if marker in text:
        text = text.replace(marker, funcs + "\n  " + marker)
        print("Inserted window.setAgentExecutionMode and window.setAgentConcurrency")
    else:
        print("Marker not found!")

# 2. Add [data-set-execution-mode] to closest selector
sel_marker = '"[data-slash-pick], '
sel_replacement = '"[data-set-execution-mode], [data-slash-pick], '
if sel_replacement not in text and sel_marker in text:
    text = text.replace(sel_marker, sel_replacement, 1)
    print("Added [data-set-execution-mode] to click delegation selector")

# 3. Add handler in click event
click_hook_target = 'if (target.hasAttribute("data-slash-pick")) {'
click_hook_code = """if (target.hasAttribute("data-set-execution-mode")) {
        const mode = target.getAttribute("data-set-execution-mode");
        if (mode) {
          window.setAgentExecutionMode(mode);
          return;
        }
      }

      """
if click_hook_target in text and "data-set-execution-mode" not in text[text.find(click_hook_target)-200:text.find(click_hook_target)]:
    text = text.replace(click_hook_target, click_hook_code + click_hook_target, 1)
    print("Added click handler for data-set-execution-mode")

# 4. Add change listener for concurrency selector
change_hook = """
    document.body.addEventListener("change", (e) => {
      const target = e.target;
      if (target && target.hasAttribute("data-set-execution-concurrency")) {
        window.setAgentConcurrency(target.value);
      }
    });
"""
if "data-set-execution-concurrency" not in text[text.find("document.body.addEventListener(\"click\""):]:
    click_end = 'document.body.addEventListener("click", async (e) => {'
    text = text.replace(click_end, change_hook + "\n    " + click_end, 1)
    print("Added change listener for data-set-execution-concurrency")

app_js_path.write_text(text, encoding="utf-8")
print("Done updating app.js!")

