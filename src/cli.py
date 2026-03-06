"""Interactive TUI for querying the Adamant codebase."""

import random
import re
import sys
import os
import shutil
import threading
import time

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    os.system("")  # Enable ANSI escape codes on Windows

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.feedback.store import init_feedback_db, save_feedback
from src.synthesis.chain import query_stream, _get_embeddings, _get_pinecone_indexes, _get_llm, _get_prompt, _get_cohere_client
from src.models import QueryResult

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

# ── Suggested questions ──────────────────────────────────────
SUGGESTED_QUESTIONS = [
    "How does Adamant's command router dispatch commands to components?",
    "How does cFE Executive Services manage application lifecycle?",
    "How does CubeDOS handle message passing between modules?",
    "How do these frameworks handle telemetry packaging and downlink?",
    "What is the OSAL abstraction layer in cFS and what does it provide?",
    "How does Adamant's fault correction component handle faults?",
    "Compare how Adamant and CubeDOS structure their task/component models.",
]

# ── Launch phrases ──────────────────────────────────────────
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

# ── Rocket animation frames ────────────────────────────────
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


def _get_width() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def _visible_len(text: str) -> int:
    """Length of text without ANSI escape codes."""
    return len(re.sub(r'\033\[[^m]*m', '', text))


def _center(text: str, width: int) -> str:
    """Center text accounting for ANSI escape codes."""
    pad = max(0, (width - _visible_len(text)) // 2)
    return " " * pad + text


def _box(lines: list, width: int, title: str = "", color: str = DARK_GRAY, pad: int = 2) -> str:
    """Draw a Unicode box around content lines."""
    inner = width - (pad * 2) - 2  # account for border chars + padding

    out = []

    # Top border with optional title
    if title:
        t_visible = len(title)
        remaining = inner - t_visible - 2
        left_bar = remaining // 2
        right_bar = remaining - left_bar
        out.append(f"{' ' * pad}{color}\u250c{'─' * left_bar} {RESET}{BOLD}{title}{RESET}{color} {'─' * right_bar}\u2510{RESET}")
    else:
        out.append(f"{' ' * pad}{color}\u250c{'─' * inner}\u2510{RESET}")

    # Content
    for line in lines:
        vis = _visible_len(line)
        right_pad = max(0, inner - vis - 1)
        out.append(f"{' ' * pad}{color}\u2502{RESET} {line}{' ' * right_pad}{color}\u2502{RESET}")

    # Bottom border
    out.append(f"{' ' * pad}{color}\u2514{'─' * inner}\u2518{RESET}")

    return "\n".join(out)


TITLE_ART = f"""{CYAN}{BOLD}
   ██████╗ ██████╗  ██████╗ ██╗   ██╗███╗   ██╗██████╗
  ██╔════╝ ██╔══██╗██╔═══██╗██║   ██║████╗  ██║██╔══██╗
  ██║  ███╗██████╔╝██║   ██║██║   ██║██╔██╗ ██║██║  ██║
  ██║   ██║██╔══██╗██║   ██║██║   ██║██║╚██╗██║██║  ██║
  ╚██████╔╝██║  ██║╚██████╔╝╚██████╔╝██║ ╚████║██████╔╝
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═════╝
  ████████╗██████╗ ██╗   ██╗████████╗██╗  ██╗
  ╚══██╔══╝██╔══██╗██║   ██║╚══██╔══╝██║  ██║
     ██║   ██████╔╝██║   ██║   ██║   ███████║
     ██║   ██╔══██╗██║   ██║   ██║   ██╔══██║
     ██║   ██║  ██║╚██████╔╝   ██║   ██║  ██║
     ╚═╝   ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚═╝
{RESET}{DARK_GRAY}      Flight Software Codebase Intelligence{RESET}
"""


class RocketSpinner:
    """Animated rocket with rotating launch phrases."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        phrase = random.choice(LAUNCH_PHRASES)
        self._thread = threading.Thread(target=self._spin, args=(phrase,), daemon=True)
        self._thread.start()

    def _spin(self, phrase: str):
        frame_idx = 0
        rocket_height = len(ROCKET_FRAMES[0])

        sys.stdout.write(HIDE_CURSOR)
        sys.stdout.flush()

        while not self._stop.is_set():
            rocket = ROCKET_FRAMES[frame_idx % len(ROCKET_FRAMES)]

            lines = []
            for i, rline in enumerate(rocket):
                if i == 4:
                    lines.append(f"  {rline}    {DARK_GRAY}{phrase}{'.' * ((frame_idx % 3) + 1)}{RESET}")
                else:
                    lines.append(f"  {rline}")

            if frame_idx > 0:
                sys.stdout.write(f"\033[{rocket_height}A")

            for line in lines:
                sys.stdout.write(f"{CLEAR_LINE}{line}\n")
            sys.stdout.flush()

            frame_idx += 1
            time.sleep(0.2)

        # Clear rocket lines
        sys.stdout.write(f"\033[{rocket_height}A")
        for _ in range(rocket_height):
            sys.stdout.write(f"{CLEAR_LINE}\n")
        sys.stdout.write(f"\033[{rocket_height}A")
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()


def _print_header() -> None:
    w = _get_width()
    print(f"\n  {DARK_GRAY}{'=' * (w - 4)}{RESET}")
    for line in TITLE_ART.strip().split("\n"):
        print(line)
    print(f"  {DARK_GRAY}{'=' * (w - 4)}{RESET}")
    print()


def _print_suggestions() -> None:
    w = _get_width()
    max_q_len = w - 14  # account for box borders, padding, and "[N] "
    lines = []
    for i, q in enumerate(SUGGESTED_QUESTIONS, 1):
        display = q if len(q) <= max_q_len else q[:max_q_len - 3] + "..."
        lines.append(f"{CYAN}{BOLD}[{i}]{RESET} {GRAY}{display}{RESET}")
    print(_box(lines, w, title="Try a question", color=CYAN))
    print()


def _print_help() -> None:
    w = _get_width()
    lines = [
        f"{CYAN}{BOLD}/help{RESET}       {GRAY}Show this help message{RESET}",
        f"{CYAN}{BOLD}/criticize{RESET}  {GRAY}Submit feedback on the last answer{RESET}",
        f"{CYAN}{BOLD}/quit{RESET}       {GRAY}Exit Adamant{RESET}",
        f"",
        f"{GRAY}Type a number {WHITE}1-{len(SUGGESTED_QUESTIONS)}{GRAY} to pick a suggested question,{RESET}",
        f"{GRAY}or type any natural language query.{RESET}",
    ]
    print()
    print(_box(lines, w, title="Commands", color=YELLOW))
    print()


def _print_status_bar(w: int) -> None:
    print(f"  {DARK_GRAY}{'─' * (w - 4)}{RESET}")


def _wrap_text(text: str, max_width: int) -> list:
    """Word-wrap text into lines no longer than max_width."""
    result = []
    for para in text.split("\n"):
        if not para.strip():
            result.append("")
            continue
        while _visible_len(para) > max_width:
            cut = para[:max_width].rfind(" ")
            if cut <= 0:
                cut = max_width
            result.append(para[:cut])
            para = para[cut:].lstrip()
        result.append(para)
    return result


def _print_streamed_result(question: str, answer: str, result, w: int) -> None:
    """Print the final formatted result after streaming completes."""

    # ── Sources ──
    if result.sources:
        src_lines = []
        for i, src in enumerate(result.sources, 1):
            c = src.chunk
            score_val = src.score
            if score_val > 0.7:
                bar_color = GREEN
            elif score_val > 0.4:
                bar_color = YELLOW
            else:
                bar_color = RED
            filled = int(score_val * 10)
            bar = f"{bar_color}{'#' * filled}{DARK_GRAY}{'.' * (10 - filled)}{RESET}"

            path = c.file_path
            if len(path) > 50:
                path = "..." + path[-47:]
            src_lines.append(
                f"{GRAY}{i}.{RESET} {bar} {WHITE}{path}{RESET}"
                f"{DARK_GRAY}:{c.start_line}-{c.end_line} ({c.chunk_type}){RESET}"
            )
        print()
        print(_box(src_lines, w, title="Sources", color=CYAN))

    # ── Latency ──
    ms = result.latency_ms
    if ms < 2000:
        lat_color = GREEN
        label = "fast"
    elif ms < 4000:
        lat_color = YELLOW
        label = "ok"
    else:
        lat_color = RED
        label = "slow"
    print(f"\n  {DARK_GRAY}Response time:{RESET} {lat_color}{ms:.0f}ms{RESET} {DARK_GRAY}({label}){RESET}")
    _print_status_bar(w)
    print()


def main() -> None:
    init_feedback_db()
    _print_header()

    spinner = RocketSpinner()
    spinner.start()

    # Pre-initialize all singletons so first query is fast
    _get_embeddings()
    _get_pinecone_indexes()
    _get_llm()
    _get_prompt()
    _get_cohere_client()

    spinner.stop()

    w = _get_width()

    # Status line
    print(f"  {GREEN}{BOLD}Systems nominal.{RESET} {GRAY}Ready for queries.{RESET}")
    print()

    # Show suggested questions
    _print_suggestions()

    # Prompt hint
    print(f"  {DARK_GRAY}Type a number, a question, or /help{RESET}")
    print()

    last_query = None
    last_answer = None

    while True:
        try:
            user_input = input(f"  {MAGENTA}{BOLD}>{RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n  {DARK_GRAY}Mission complete. Goodbye!{RESET}\n")
            break

        if not user_input:
            continue

        # Check for number shortcut
        question = None
        if user_input.isdigit():
            idx = int(user_input)
            if 1 <= idx <= len(SUGGESTED_QUESTIONS):
                question = SUGGESTED_QUESTIONS[idx - 1]
            else:
                print(f"\n  {DARK_GRAY}Pick a number between 1 and {len(SUGGESTED_QUESTIONS)}, or type a question.{RESET}\n")
                continue

        if user_input == "/quit":
            print(f"\n  {DARK_GRAY}Mission complete. Goodbye!{RESET}\n")
            break
        elif user_input == "/help":
            _print_help()
            continue
        elif user_input == "/criticize":
            if last_query is None:
                print(f"\n  {DARK_GRAY}No previous query to provide feedback on.{RESET}\n")
                continue
            try:
                feedback_text = input(f"  {GRAY}Feedback > {RESET}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n  {DARK_GRAY}Cancelled.{RESET}")
                continue
            if feedback_text:
                save_feedback(last_query, last_answer, feedback_text)
                print(f"  {GREEN}Feedback saved. Thank you!{RESET}\n")
            else:
                print(f"  {DARK_GRAY}Empty feedback, not saved.{RESET}\n")
            continue

        # Use the resolved question (from number) or raw input
        if question is None:
            question = user_input

        w = _get_width()

        spinner.start()
        try:
            stream = query_stream(question)
            result = None
            first_token = True

            for chunk in stream:
                if isinstance(chunk, QueryResult):
                    result = chunk
                else:
                    if first_token:
                        spinner.stop()
                        # Print query box
                        q_lines = _wrap_text(f"{WHITE}{question}{RESET}", w - 10)
                        print()
                        print(_box(q_lines, w, title="Query", color=MAGENTA))
                        print()
                        # Start answer section
                        inner_w = w - 8
                        print(f"  {DARK_GRAY}\u250c{'─' * 4} {RESET}{BOLD}Answer{RESET}{DARK_GRAY} {'─' * (inner_w - 10)}\u2510{RESET}")
                        print(f"  {DARK_GRAY}\u2502{RESET} ", end="")
                        first_token = False
                    sys.stdout.write(chunk)
                    sys.stdout.flush()

            if first_token:
                spinner.stop()

            # Close the answer box
            inner_w = w - 8
            print(f"\n  {DARK_GRAY}\u2514{'─' * inner_w}\u2518{RESET}")

            if result:
                last_query = question
                last_answer = result.answer
                _print_streamed_result(question, result.answer, result, w)

        except Exception as e:
            spinner.stop()
            print(f"\n  {RED}Error: {e}{RESET}\n")
            last_query = None
            last_answer = None


if __name__ == "__main__":
    main()
