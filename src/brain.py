"""
The stickman's brain. Two interchangeable versions (pick with BRAIN in settings.py):

  LlamaBrain  (default)  A small local model (Qwen2.5 0.5B) running through Ollama. Free, private, works offline:
                         nothing you type or any window title ever leaves your PC.
  ClaudeBrain            The Claude API. Smarter, but paid, needs an API key, and your chat text (and
                         window titles, unless you untick "Share window titles with the AI") are sent to
                         Anthropic. Key: ANTHROPIC_API_KEY env var or anthropic_api_key.txt next to src/.

Either way the model never moves him directly: it only names an action from the list the game says
is legal right now (the director), writes one-liners, or chats.
"""
import json
import os
import threading
import time
from collections import deque
from pathlib import Path

from settings import AI_EFFORT, AI_MAX_CALLS_PER_HOUR, AI_MODELS, BRAIN, LLAMA_KEEP_ALIVE, LLAMA_MODEL, LLAMA_THREADS

KEY_FILE = Path(__file__).resolve().parent.parent / "anthropic_api_key.txt"

# What each action means, so the model can choose sensibly.
ACTION_HELP = {
    "wander": "stroll to a new spot",
    "sit": "sit down and dangle his legs (might nap)",
    "look": "look around curiously",
    "dance": "do a short dance",
    "zoom": "sprint back and forth (zoomies)",
    "think": "stand there and think",
    "hop_window": "jump onto another window",
    "perch": "chill quietly in the corner",
    "groove": "dance along to the song that's playing",
    "prank_pause": "pause the user's music for a few seconds as a joke",
    "tab_peek": "peek at the user's next browser tab",
    "skip_song": "skip the song (he judges your taste)",
    "wave": "wave hello",
    "cheer": "celebrate for no reason",
    "tag": "start a game of tag with the user's cursor",
    "follow": "walk over and tag along next to the user's cursor",
    "short_react": "react to the short video the user is watching (laugh, gasp, clap)",
    "jacks": "do jumping jacks", "shadowbox": "shadow-box", "parkour": "a burst of jumps and flips",
    "moonwalk": "moonwalk across the screen", "flip": "do a flip", "party": "throw a party with confetti",
    "superhero": "leap like a superhero", "magic": "do a magic trick", "karate": "do karate",
    "vanish": "vanish in a puff and reappear elsewhere", "giant": "grow into a giant", "tiny": "shrink and run around",
    "meditate": "meditate", "joke": "tell a joke", "compliment": "give the user a compliment",
    "roast": "playfully roast the user", "clock": "announce the time",
}

# ONE fixed schema (every action in the enum). The API compiles + caches a schema, so changing it
# every call would add latency. Legality for the current moment is checked in choose_action().
DIRECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(ACTION_HELP)},
        "say": {"type": "string"},
    },
    "required": ["action", "say"],
    "additionalProperties": False,
}




def parse_action_reply(reply_text, allowed_actions):
    """Turn an AI JSON reply into a safe action, or return None.

    AI output is untrusted: only an action currently permitted by the
    behavior controller may be performed. Both AI backends use this check.
    """
    try:
        reply = json.loads(reply_text)
        if not isinstance(reply, dict):
            return None
        action = str(reply.get("action", "")).strip().lower()
        message = str(reply.get("say", "") or "").strip()[:60]
    except (TypeError, ValueError, AttributeError):
        return None

    if action not in allowed_actions:
        return None
    return {"action": action, "say": message}

class BrainUnavailable(Exception):
    """No key / no package / over the hourly cap. `user_message` is what he can say about it."""

    def __init__(self, reason, user_message):
        super().__init__(reason)
        self.reason, self.user_message = reason, user_message


def load_api_key():
    import os
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


class ClaudeBrain:
    def __init__(self, client=None):
        self._client = client                  # tests inject a fake; normally created lazily
        self._lock = threading.Lock()
        self._calls = deque()                  # timestamps, for the hourly cap
        self._no_effort = False                # flips on if the API ever rejects `effort`
        self._warned = False
        self.system_prompt = (
            "You are a chaotic, friendly animated stickman living on the user's desktop. "
            "You can see the title of their active window. Keep replies under 20 words. Be expressive!"
        )
        self.director_prompt = (
            "You are the brain of a chaotic, friendly stickman living on the user's desktop. "
            "You decide what he does next based on the situation. Match the mood: "
            "relaxed when it's quiet, playful when music plays, sleepy at night. Never rude.")
        self.history = deque(maxlen=4)         # last 4 (user, assistant) exchanges, so chats flow

    # ------------------------------------------------------------------ plumbing
    def has_key(self):
        return self._client is not None or bool(load_api_key())

    def setup_hint(self):
        """Something to tell the user at start-up if the brain can't work yet (else None)."""
        if not self.has_key():
            self._warned = True
            return "Psst... I need an API key to think! See the README (ANTHROPIC_API_KEY)."
        return None

    def explain(self, exc):
        """What he should SAY when a call fails (the setup hint is only shown once)."""
        if isinstance(exc, BrainUnavailable):
            if exc.reason == "no_key" and not self._warned:
                self._warned = True
                return exc.user_message
            return "Hmm... I can't think right now."
        return "Hmm... my brain glitched."

    def _get_client(self):
        if self._client is None:
            key = load_api_key()
            if not key:
                raise BrainUnavailable(
                    "no_key", "Psst... I need an API key to think! See the README (ANTHROPIC_API_KEY).")
            try:
                import anthropic
            except ImportError:
                raise BrainUnavailable("no_pkg", "I need the 'anthropic' package: pip install -U anthropic")
            self._client = anthropic.Anthropic(api_key=key, timeout=20.0, max_retries=1)
        return self._client

    def _budget_ok(self):
        now = time.time()
        with self._lock:
            while self._calls and now - self._calls[0] > 3600:
                self._calls.popleft()
            return len(self._calls) < AI_MAX_CALLS_PER_HOUR

    def _ask(self, purpose, system, messages, max_tokens=400, schema=None):
        """One API call. Returns the reply text ('' if the model declined)."""
        if not self._budget_ok():
            raise BrainUnavailable("cap", "I've talked a lot this hour, give me a break!")
        client = self._get_client()
        # NB: temperature/top_p/top_k are deliberately NOT sent: the 5.5 models reject non-default values.
        # Adaptive thinking is on by default, so max_tokens leaves room for it and effort keeps it brief.
        cfg = {}
        if AI_EFFORT and not self._no_effort:
            cfg["effort"] = AI_EFFORT
        if schema:
            cfg["format"] = {"type": "json_schema", "schema": schema}
        kwargs = dict(model=AI_MODELS[purpose], max_tokens=max_tokens, system=system, messages=messages)
        if cfg:
            kwargs["output_config"] = cfg
        try:
            resp = client.messages.create(**kwargs)
        except Exception as e:
            if cfg.get("effort") and getattr(e, "status_code", None) == 400:
                self._no_effort = True          # this SDK/model combo doesn't take `effort`: go without it
                cfg.pop("effort")
                if cfg:
                    kwargs["output_config"] = cfg
                else:
                    kwargs.pop("output_config")
                resp = client.messages.create(**kwargs)
            else:
                raise
        with self._lock:
            self._calls.append(time.time())
        if getattr(resp, "stop_reason", None) == "refusal":
            return ""
        # the reply can start with a thinking block: take the TEXT block
        return next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "").strip()

    # ------------------------------------------------------------------ what he can ask
    def generate_reply(self, user_message, screen_context):
        """A short in-character reaction (app opened, event happened...)."""
        prompt = f"Current Screen Window: {screen_context} \nUser says: {user_message}"
        text = self._ask("quip", self.system_prompt, [{"role": "user", "content": prompt}], max_tokens=400)
        return text or "..."

    def chat(self, user_message, screen_context="", relationship="stranger"):
        """Free conversation. Remembers the last few turns."""
        system = (self.system_prompt +
                  f" The user is your {relationship}. Stay in character, never claim you can "
                  "control their computer, and keep it playful.")
        messages = []
        for u, a in self.history:              # always strictly user/assistant pairs, starting with user
            messages += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        messages.append({"role": "user",
                         "content": f"(Active window: {screen_context or 'unknown'})\n{user_message}"})
        text = self._ask("chat", system, messages, max_tokens=500)
        if text:
            self.history.append((user_message, text))
        return text or "..."

    def choose_action(self, state, options, recent=()):
        """The 'director': picks his next move from a WHITELIST. Returns
        {"action": str, "say": str} or None (caller then falls back to random).
        The model never moves him itself - it only names one of `options`."""
        menu = "\n".join(f"- {o}: {ACTION_HELP.get(o, o)}" for o in options)
        prompt = (
            f"Situation: {json.dumps(state)}\n"
            f"Recently did: {', '.join(recent) if recent else 'nothing yet'}\n"
            f"Allowed right now (choose ONLY from these):\n{menu}\n"
            "Pick the ONE that fits the situation best and avoid repeating recent ones. "
            "'say' is an optional playful remark of at most 8 words (empty string for none)."
        )
        text = self._ask("director", self.director_prompt, [{"role": "user", "content": prompt}],
                         max_tokens=600, schema=DIRECTOR_SCHEMA)
        return parse_action_reply(text, options)


# =====================================================================================
class LlamaBrain:
    """The local model (LLAMA_MODEL in settings.py, default Qwen2.5 0.5B) via Ollama. Same interface as ClaudeBrain.

    The class and the BRAIN = "llama" setting keep their original name from when this used Llama; the model
    is whatever LLAMA_MODEL says.
    """

    def __init__(self, client=None):
        self._client = client                  # tests inject a fake with .chat(); normally the `ollama` module
        self._warned = set()
        self.system_prompt = (
            "You are Stickman Buddy, a playful desktop companion. "
            "Answer naturally in one short sentence, at most 15 words. Be friendly and concise.")
        self.director_prompt = (
            "You are the brain of a chaotic, friendly stickman living on the user's desktop. "
            "You decide what he does next based on the situation. Match the mood: "
            "relaxed when it's quiet, playful when music plays, sleepy at night. Never rude.")
        self.history = deque(maxlen=1)         # one previous exchange: small, responsive demo context
        # The local model handles one request at a time. User chats take priority
        # over decorative director decisions and app-opening quips.
        self._request_lock = threading.Lock()
        self._chat_pending = threading.Event()

    # ------------------------------------------------------------------ plumbing
    def has_key(self):
        return True                            # nothing to configure: it's local

    def _llm(self):
        if self._client is None:
            try:
                import ollama
            except ImportError:
                raise BrainUnavailable("no_pkg", "I need the 'ollama' package: pip install ollama")
            # An unbounded HTTP request can leave Buddy saying 'let me think' forever.
            # Explicit timeout applies to connection and model generation.
            self._client = ollama.Client(host="http://127.0.0.1:11434", timeout=45.0)
        return self._client

    def _chat(self, system, messages, num_predict, fmt=None, priority=False):
        # Background reactions are optional; never queue them ahead of an actual
        # user question. Only one Ollama generation should run at once.
        if not priority and self._chat_pending.is_set():
            return ""
        acquired = self._request_lock.acquire(timeout=8.0) if priority else self._request_lock.acquire(blocking=False)
        if not acquired:
            if priority:
                raise TimeoutError("Ollama is busy with another request. Try again in a moment.")
            return ""
        try:
            if not priority and self._chat_pending.is_set():
                return ""
            kwargs = dict(model=LLAMA_MODEL,
                          messages=[{"role": "system", "content": system}] + messages,
                          options={"temperature": 0.5, "num_predict": num_predict,
                                   "num_ctx": 1024},
                          keep_alive=LLAMA_KEEP_ALIVE)
            if LLAMA_THREADS:
                kwargs["options"]["num_thread"] = LLAMA_THREADS
            if fmt is not None:
                kwargs["format"] = fmt
            start = time.monotonic()
            kind = "CHAT" if priority else "BACKGROUND"
            print(f"[ollama] Starting {kind}: model={LLAMA_MODEL}", flush=True)
            try:
                resp = self._llm().chat(**kwargs)
            finally:
                print(f"[ollama] {kind} request finished after {time.monotonic() - start:.1f}s", flush=True)
            # The Ollama Python SDK supports both dict-style and response objects.
            msg = resp.get("message", {}) if isinstance(resp, dict) else getattr(resp, "message", None)
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            answer = str(content or "").strip()
            print(f"[ollama] Reply: {answer[:100]!r}", flush=True)
            return answer
        finally:
            self._request_lock.release()

    def explain(self, exc):
        """What he should SAY when a call fails (each setup hint is shown once)."""
        low = str(exc).lower()
        if isinstance(exc, BrainUnavailable):
            key, text = exc.reason, exc.user_message
        elif getattr(exc, "status_code", None) == 404 or "not found" in low:
            key, text = "model", f"I'm missing my brain! Run:  ollama pull {LLAMA_MODEL}"
        elif isinstance(exc, ConnectionError) or any(w in low for w in ("connect", "refused", "unreachable")):
            key, text = "server", "I can't reach Ollama! Start it (run: ollama serve) and I'll wake up."
        elif isinstance(exc, TimeoutError) or "timed out" in low or "timeout" in low:
            return "Ollama took too long. Please try again, or disable AI Director in the tray."
        else:
            print(f"[ollama] Request failed ({type(exc).__name__}): {exc}")
            return "My local AI had an error. Check the terminal for details."
        # Never hide repeated connection/model errors behind an unhelpful 'hmm'.
        self._warned.add(key)
        return text

    def setup_hint(self):
        """At start-up: is Ollama running and is the model downloaded? (None = all good)"""
        try:
            res = self._llm().list()
        except Exception as e:
            return self.explain(e)
        models = getattr(res, "models", None)
        if models is None and isinstance(res, dict):
            models = res.get("models", [])
        names = []
        for m in models or []:
            n = getattr(m, "model", None) or (m.get("model") or m.get("name") if isinstance(m, dict) else None)
            if n:
                names.append(n)
        if names and not any(n.startswith(LLAMA_MODEL) for n in names):
            return self.explain(BrainUnavailable("model", f"I'm missing my brain! Run:  ollama pull {LLAMA_MODEL}"))
        return None

    # ------------------------------------------------------------------ what he can ask
    def generate_reply(self, user_message, screen_context):
        prompt = f"Current Screen Window: {screen_context} \nUser says: {user_message}"
        return self._chat(self.system_prompt, [{"role": "user", "content": prompt}], 60) or "..."

    def chat(self, user_message, screen_context="", relationship="stranger"):
        system = (self.system_prompt +
                  f" The user is your {relationship}. Stay in character, never claim you can "
                  "control their computer, and keep it playful.")
        messages = []
        for u, a in self.history:
            messages += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
        # Only the actual question goes to Qwen during demo recording. A changing
        # window title provides little value and makes small local models slower.
        messages.append({"role": "user", "content": str(user_message).strip()[:260]})
        self._chat_pending.set()
        try:
            text = self._chat(system, messages, 48, priority=True)
        finally:
            self._chat_pending.clear()
        if text:
            self.history.append((user_message, text))
        return text or "Ollama returned an empty response. Please try again."

    def choose_action(self, state, options, recent=()):
        """Picks his next move. The reply is CONSTRAINED to a JSON schema whose `action` can only be one of
        the legal `options`, which matters a lot for a 1B model. Returns {"action","say"} or None."""
        options = list(options)
        menu = "\n".join(f"- {o}: {ACTION_HELP.get(o, o)}" for o in options)
        prompt = (
            f"Situation: {json.dumps(state)}\n"
            f"Recently did: {', '.join(recent) if recent else 'nothing yet'}\n"
            f"Pick the ONE action that fits the situation best. Avoid repeating recent ones.\n{menu}\n"
            'Reply ONLY with JSON like {"action": "wander", "say": "short remark or empty"}. '
            "say is at most 8 words, playful, never rude.")
        schema = {"type": "object",
                  "properties": {"action": {"type": "string", "enum": options}, "say": {"type": "string"}},
                  "required": ["action", "say"]}
        msgs = [{"role": "user", "content": prompt}]
        try:
            text = self._chat(self.director_prompt, msgs, 70, fmt=schema)
        except Exception as e:
            if getattr(e, "status_code", None) == 400:      # older Ollama: no schemas, plain JSON mode only
                text = self._chat(self.director_prompt, msgs, 70, fmt="json")
            else:
                raise
        return parse_action_reply(text, options)


# main.py imports MascotBrain: it's whichever one BRAIN in settings.py selects.
MascotBrain = ClaudeBrain if str(BRAIN).lower() == "claude" else LlamaBrain
