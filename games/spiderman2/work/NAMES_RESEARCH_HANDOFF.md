# SM2 names research handoff (for a fresh Google/Antigravity agent)

The agent RESEARCHES the canonical Hebrew name for each Spider-Man 2 character/place/org
token (Wikipedia / Hebrew Marvel sources) and fills it into `names_research.json`. It does
the research+translation ITSELF — NOT a local model / API. Claude then applies the registry
deterministically (`names_apply.py`) across the spine and rebakes.

File to edit (in place): `C:\Users\Nehoray_Cohen\Projects\Game translator\games\spiderman2\work\names_research.json`
Shape: `{ "Token": {"count": N, "examples": ["...hebrew context..."], "hebrew": ""}, ... }`
For each token, set its `hebrew` value. ~88 are PRE-FILLED (verify them); ~214 are blank.

The paste-ready instruction is in the chat (and below).
