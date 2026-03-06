"""ANSI rendering functions for the web terminal.

All functions return strings with \\r\\n line endings (xterm.js raw mode).
Extracted from src/cli.py -- the CLI continues to work standalone.
"""

# ── ANSI codes ──────────────────────────────────────────────
DIM = "\033[2m"
BOLD = "\033[1m"
ITALIC = "\033[3m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
RED = "\033[31m"
WHITE = "\033[97m"
ORANGE = "\033[38;5;208m"
GRAY = "\033[38;5;245m"
DARK_GRAY = "\033[38;5;240m"
BLUE = "\033[38;5;39m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

# ── Box-drawing characters ─────────────────────────────────
HLINE = "\u2500"       # horizontal line
TL = "\u250c"          # top-left corner
TR = "\u2510"          # top-right corner
BL = "\u2514"          # bottom-left corner
BR = "\u2518"          # bottom-right corner
VLINE = "\u2502"       # vertical line
DHLINE = "\u2550"      # double horizontal line
BLOCK_FULL = "\u2588"  # full block
BLOCK_LIGHT = "\u2591" # light shade

# ── Prompt strings ─────────────────────────────────────────
PROMPT_STR = f"  {MAGENTA}{BOLD}>{RESET} "
FEEDBACK_PROMPT_STR = f"  {GRAY}Feedback > {RESET}"

# ── Suggested questions ────────────────────────────────────
SUGGESTED_QUESTIONS = [
    "How does the command router dispatch commands to components?",
    "How does the CCSDS packetizer create telemetry packets?",
    "What types of queues are available and what are the differences between them?",
    "How does the command sequencer execute stored command sequences?",
    "What is the product database and how does it manage data products?",
    "How does the task watchdog detect and handle unresponsive tasks?",
    "How does the fault correction component handle and respond to faults?",
]

# ── Launch phrases ─────────────────────────────────────────
LAUNCH_PHRASES = [
    "Ignition sequence started",
    "T-minus 10... all systems nominal",
    "Main engine throttle up",
    "Solid rocket boosters engaged",
    "Clearing the tower",
    "Go for throttle up",
    "Staging confirmed, second stage ignition",
    "Telemetry acquisition locked",
    "Vehicle is supersonic",
    "Max Q, standing by",
    "Fairing separation confirmed",
    "Orbital insertion burn in progress",
    "Flight dynamics reports nominal trajectory",
    "MECO. Main engine cutoff confirmed",
    "Payload deploy sequence initiated",
    "Downrange tracking station acquired",
    "Roll program complete",
]

# ── Rocket animation frames ───────────────────────────────
ROCKET_FRAMES = [
    [
        f"      {ORANGE}/\\{RESET}",
        f"     {WHITE}/  \\{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"     {GRAY}\\  /{RESET}",
        "      " + RED + "}}" + RESET,
        f"      {ORANGE}/\\{RESET}",
        f"     {YELLOW}~{RED}~~{YELLOW}~{RESET}",
    ],
    [
        f"      {ORANGE}/\\{RESET}",
        f"     {WHITE}/  \\{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"     {GRAY}\\  /{RESET}",
        "      " + RED + "}}" + RESET,
        f"     {YELLOW}~{ORANGE}~~{YELLOW}~{RESET}",
        f"    {YELLOW}~{RED}~~~~{YELLOW}~{RESET}",
    ],
    [
        f"      {ORANGE}/\\{RESET}",
        f"     {WHITE}/  \\{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"     {GRAY}\\  /{RESET}",
        "      " + RED + "}}" + RESET,
        f"    {RED}~{ORANGE}~~~~{RED}~{RESET}",
        f"   {YELLOW}~{RED}~~~~~~{YELLOW}~{RESET}",
    ],
    [
        f"      {ORANGE}/\\{RESET}",
        f"     {WHITE}/  \\{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"    {WHITE}|    |{RESET}",
        f"     {GRAY}\\  /{RESET}",
        "      " + RED + "}}" + RESET,
        f"     {ORANGE}~{YELLOW}~~{ORANGE}~{RESET}",
        f"    {RED}~{YELLOW}~~~~{RED}~{RESET}",
    ],
]

ROCKET_HEIGHT = len(ROCKET_FRAMES[0])

# ── Title art ──────────────────────────────────────────────
TITLE_ART = (
    f"{CYAN}{BOLD}\n"
    "  \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2557   \u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2557   \u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2557\n"
    "  \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2557 \u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2557\u2588\u2588\u2588\u2588\u2557  \u2588\u2588\u2551\u255a\u2550\u2550\u2588\u2588\u2554\u2550\u2550\u255d\n"
    "  \u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2554\u2588\u2588\u2588\u2588\u2554\u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2551\u2588\u2588\u2554\u2588\u2588\u2557 \u2588\u2588\u2551   \u2588\u2588\u2551\n"
    "  \u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u2588\u2588\u2551\u255a\u2588\u2588\u2554\u255d\u2588\u2588\u2551\u2588\u2588\u2554\u2550\u2550\u2588\u2588\u2551\u2588\u2588\u2551\u255a\u2588\u2588\u2557\u2588\u2588\u2551   \u2588\u2588\u2551\n"
    "  \u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2588\u2588\u2588\u2588\u2554\u255d\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2551 \u255a\u2550\u255d \u2588\u2588\u2551\u2588\u2588\u2551  \u2588\u2588\u2551\u2588\u2588\u2551 \u255a\u2588\u2588\u2588\u2588\u2551   \u2588\u2588\u2551\n"
    "  \u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u2550\u2550\u2550\u2550\u255d \u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u255d     \u255a\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u255d\u255a\u2550\u255d  \u255a\u2550\u2550\u2550\u255d   \u255a\u2550\u255d\n"
    f"{RESET}{DARK_GRAY}              Ada Codebase Intelligence{RESET}"
)


def _box(lines: list, width: int, title: str = "", color: str = DARK_GRAY) -> str:
    """Draw a Unicode box around content lines. Returns string with \\r\\n endings."""
    inner = width - 6  # 2 pad + 2 border chars + 2 inner pad

    out = []

    # Top border with optional title
    if title:
        t_visible = len(title)
        remaining = inner - t_visible - 2
        left_bar = remaining // 2
        right_bar = remaining - left_bar
        out.append(f"  {color}{TL}{HLINE * left_bar} {RESET}{BOLD}{title}{RESET}{color} {HLINE * right_bar}{TR}{RESET}")
    else:
        out.append(f"  {color}{TL}{HLINE * inner}{TR}{RESET}")

    # Content lines
    for line in lines:
        out.append(f"  {color}{VLINE}{RESET} {line}")

    # Bottom border
    out.append(f"  {color}{BL}{HLINE * inner}{BR}{RESET}")

    return "\r\n".join(out)


def render_header(width: int) -> str:
    """Render the full header with border and title art."""
    border = DHLINE * (width - 4)
    parts = []
    parts.append(f"\r\n  {DARK_GRAY}{border}{RESET}")
    for line in TITLE_ART.strip().split("\n"):
        parts.append(line)
    parts.append(f"  {DARK_GRAY}{border}{RESET}")
    parts.append("")
    return "\r\n".join(parts) + "\r\n"


def render_suggestions(width: int) -> str:
    """Render the suggested questions box."""
    max_q_len = width - 14  # account for box + "[N] "
    lines = []
    for i, q in enumerate(SUGGESTED_QUESTIONS, 1):
        display = q if len(q) <= max_q_len else q[:max_q_len - 3] + "..."
        lines.append(f"{CYAN}{BOLD}[{i}]{RESET} {GRAY}{display}{RESET}")
    return _box(lines, width, title="Try a question", color=CYAN) + "\r\n"


def render_help(width: int) -> str:
    """Render the help box."""
    n = len(SUGGESTED_QUESTIONS)
    lines = [
        f"{CYAN}{BOLD}/help{RESET}       {GRAY}Show this help message{RESET}",
        f"{CYAN}{BOLD}/criticize{RESET}  {GRAY}Submit feedback on the last answer{RESET}",
        f"{CYAN}{BOLD}/quit{RESET}       {GRAY}Exit Adamant{RESET}",
        "",
        f"{GRAY}Type a number {WHITE}1-{n}{GRAY} to pick a suggested question,{RESET}",
        f"{GRAY}or type any natural language query.{RESET}",
    ]
    return "\r\n" + _box(lines, width, title="Commands", color=YELLOW) + "\r\n\r\n"


def render_query_box(question: str, width: int) -> str:
    """Render the query display box."""
    q_lines = [f"{WHITE}{question}{RESET}"]
    return "\r\n" + _box(q_lines, width, title="Query", color=MAGENTA) + "\r\n"


def render_answer_header(width: int) -> str:
    """Render the answer section header line (open-ended box top)."""
    inner = width - 6
    title = "Answer"
    remaining = inner - len(title) - 2
    left_bar = remaining // 2
    right_bar = remaining - left_bar
    return (
        f"\r\n  {DARK_GRAY}{TL}{HLINE * left_bar} {RESET}{BOLD}{title}{RESET}"
        f"{DARK_GRAY} {HLINE * right_bar}{TR}{RESET}\r\n"
        f"  {DARK_GRAY}{VLINE}{RESET} "
    )


def render_answer_footer(width: int) -> str:
    """Render the answer section footer (close the box)."""
    inner = width - 6
    return f"\r\n  {DARK_GRAY}{BL}{HLINE * inner}{BR}{RESET}\r\n"


def render_sources(sources: list, width: int) -> str:
    """Render the sources box from a list of RetrievedChunk objects."""
    src_lines = []
    for i, src in enumerate(sources, 1):
        c = src.chunk
        score_val = src.score
        filled = int(score_val * 10)
        empty = 10 - filled
        if score_val > 0.7:
            bar_color = GREEN
        elif score_val > 0.4:
            bar_color = YELLOW
        else:
            bar_color = RED
        bar = f"{bar_color}{'#' * filled}{DARK_GRAY}{'.' * empty}{RESET}"

        path = c.file_path
        if len(path) > 50:
            path = "..." + path[-47:]
        src_lines.append(
            f"{GRAY}{i}.{RESET} {bar} {WHITE}{path}{RESET}"
            f"{DARK_GRAY}:{c.start_line}-{c.end_line} ({c.chunk_type}){RESET}"
        )
    return "\r\n" + _box(src_lines, width, title="Sources", color=CYAN) + "\r\n"


def render_latency(latency_ms: float) -> str:
    """Render the latency footer line."""
    if latency_ms < 2000:
        lat_color = GREEN
        label = "fast"
    elif latency_ms < 4000:
        lat_color = YELLOW
        label = "ok"
    else:
        lat_color = RED
        label = "slow"
    return f"\r\n  {DARK_GRAY}Response time:{RESET} {lat_color}{latency_ms:.0f}ms{RESET} {DARK_GRAY}({label}){RESET}\r\n"


def render_rocket_frame(frame_lines: list, phrase: str, frame_idx: int) -> str:
    """Render a single rocket animation frame as a string."""
    lines = []
    for i, rline in enumerate(frame_lines):
        if i == 4:  # middle of rocket
            dots = "." * ((frame_idx % 3) + 1)
            lines.append(f"  {rline}    {DARK_GRAY}{phrase}{dots}{RESET}")
        else:
            lines.append(f"  {rline}")
    return "\r\n".join(lines) + "\r\n"


def render_clear_rocket() -> str:
    """Return ANSI sequences to clear the rocket animation area."""
    return (
        f"\033[{ROCKET_HEIGHT}A"
        + (f"{CLEAR_LINE}\r\n" * ROCKET_HEIGHT)
        + f"\033[{ROCKET_HEIGHT}A"
    )
