class ContextManager:
    def __init__(self):
        # session_id -> {"profile": {...}, "history": [...]}
        self.sessions = {}

    def get_profile(self, session_id: str):
        return self.sessions.get(session_id, {}).get("profile", {})

    def update_profile(self, session_id: str, new_profile: dict):
        session = self.sessions.setdefault(session_id, {"profile": {}, "history": []})
        session["profile"] = smart_update_profile(session["profile"], new_profile)
        return session["profile"]

    def get_history(self, session_id: str, limit: int = 5):
        history = self.sessions.get(session_id, {}).get("history", [])
        return history[-limit:]

    def add_message(self, session_id: str, role: str, content: str):
        session = self.sessions.setdefault(session_id, {"profile": {}, "history": []})
        session["history"].append({"role": role, "content": content})



def smart_update_profile(old_profile: dict, new_profile: dict) -> dict:
    """Update only non-empty fields in profile."""
    updated = old_profile.copy()
    for key, val in new_profile.items():
        if val not in [None, "", [], {}, "None"]:
            updated[key] = val
    return updated