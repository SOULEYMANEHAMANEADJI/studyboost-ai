"""Stage programmatic changes until before Streamlit renders the text widget."""
def stage_editor_text(state, text):
    state["_editor_pending"] = text


def apply_pending_editor_text(state):
    if "_editor_pending" in state:
        text = state.pop("_editor_pending")
        state["editor_text"] = text
        state["editor_textarea"] = text
        state["_last_draft"] = None


def editor_value(state):
    return state.get("editor_textarea", state.get("editor_text", ""))
