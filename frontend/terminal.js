(function () {
    "use strict";

    var WS_URL =
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1"
            ? "ws://localhost:8000/ws"
            : "wss://amusing-perfection-production.up.railway.app/ws";

    var output = document.getElementById("output");
    var input = document.getElementById("input");
    var ws = null;
    var currentAnswer = null; // element being streamed into

    // ── Rocket splash screen ──────────────────────────────

    var LAUNCH_PHRASES = [
        "Ignition sequence started",
        "T-minus 10... all systems nominal",
        "Main engine throttle up",
        "Solid rocket boosters engaged",
        "Clearing the tower",
        "Roll program initiated",
        "Go for throttle up",
        "Max Q achieved"
    ];

    var splashEl = null;
    var splashReady = false;
    var splashTimer = false;
    var splashDone = false;
    var messageBuffer = [];
    var splashInterval = null;

    function showSplash() {
        splashEl = document.createElement("div");
        splashEl.id = "splash";

        splashEl.innerHTML =
            '<div class="header">' +
            '<pre>' +
            ' ██████╗ ██████╗  ██████╗ ██╗   ██╗███╗   ██╗██████╗ \n' +
            '██╔════╝ ██╔══██╗██╔═══██╗██║   ██║████╗  ██║██╔══██╗\n' +
            '██║  ███╗██████╔╝██║   ██║██║   ██║██╔██╗ ██║██║  ██║\n' +
            '██║   ██║██╔══██╗██║   ██║██║   ██║██║╚██╗██║██║  ██║\n' +
            '╚██████╔╝██║  ██║╚██████╔╝╚██████╔╝██║ ╚████║██████╔╝\n' +
            ' ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═════╝\n' +
            '████████╗██████╗ ██╗   ██╗████████╗██╗  ██╗\n' +
            '╚══██╔══╝██╔══██╗██║   ██║╚══██╔══╝██║  ██║\n' +
            '   ██║   ██████╔╝██║   ██║   ██║   ███████║\n' +
            '   ██║   ██╔══██╗██║   ██║   ██║   ██╔══██║\n' +
            '   ██║   ██║  ██║╚██████╔╝   ██║   ██║  ██║\n' +
            '   ╚═╝   ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚═╝</pre>' +
            '<div class="subtitle">Flight Software Codebase Intelligence</div>' +
            '</div>' +
            '<div class="splash-thruster">' +
                '<div class="bar"></div><div class="bar"></div><div class="bar"></div><div class="bar"></div><div class="bar"></div>' +
            '</div>' +
            '<div class="launch-phrase"></div>';

        document.body.appendChild(splashEl);

        var phraseEl = splashEl.querySelector(".launch-phrase");
        var chosenPhrase = LAUNCH_PHRASES[Math.floor(Math.random() * LAUNCH_PHRASES.length)];
        var dots = 0;
        phraseEl.textContent = chosenPhrase + "...";

        splashInterval = setInterval(function () {
            dots = (dots + 1) % 3;
            phraseEl.textContent = chosenPhrase + ".".repeat(dots + 1);
        }, 400);

        setTimeout(function () {
            splashTimer = true;
            tryDismissSplash();
        }, 3000);
    }

    function tryDismissSplash() {
        if (splashDone || !splashReady || !splashTimer) return;
        splashDone = true;
        clearInterval(splashInterval);
        splashEl.classList.add("fade-out");
        setTimeout(function () {
            splashEl.remove();
            messageBuffer.forEach(function (msg) { handleMessage(msg); });
            messageBuffer = [];
        }, 600);
    }

    // ── Helpers ──────────────────────────────────────────

    function el(tag, cls, html) {
        var e = document.createElement(tag);
        if (cls) e.className = cls;
        if (html !== undefined) e.innerHTML = html;
        return e;
    }

    function scrollBottom() {
        requestAnimationFrame(function () {
            output.scrollTop = output.scrollHeight;
        });
    }

    function append(node) {
        output.appendChild(node);
        scrollBottom();
    }

    function sendInput(text) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "input", text: text }));
        }
    }

    var firstInteraction = false;

    function dismissGlow() {
        if (!firstInteraction) {
            firstInteraction = true;
            input.classList.remove("glow");
        }
    }

    function enableInput() {
        input.disabled = false;
        if (!firstInteraction) input.classList.add("glow");
        input.focus();
    }

    function disableInput() {
        input.disabled = true;
        input.classList.remove("glow");
    }

    // ── Renderers ────────────────────────────────────────

    function renderHeader() {
        var div = el("div", "header");
        div.innerHTML =
            '<pre>' +
            ' ██████╗ ██████╗  ██████╗ ██╗   ██╗███╗   ██╗██████╗ \n' +
            '██╔════╝ ██╔══██╗██╔═══██╗██║   ██║████╗  ██║██╔══██╗\n' +
            '██║  ███╗██████╔╝██║   ██║██║   ██║██╔██╗ ██║██║  ██║\n' +
            '██║   ██║██╔══██╗██║   ██║██║   ██║██║╚██╗██║██║  ██║\n' +
            '╚██████╔╝██║  ██║╚██████╔╝╚██████╔╝██║ ╚████║██████╔╝\n' +
            ' ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═════╝\n' +
            '████████╗██████╗ ██╗   ██╗████████╗██╗  ██╗\n' +
            '╚══██╔══╝██╔══██╗██║   ██║╚══██╔══╝██║  ██║\n' +
            '   ██║   ██████╔╝██║   ██║   ██║   ███████║\n' +
            '   ██║   ██╔══██╗██║   ██║   ██║   ██╔══██║\n' +
            '   ██║   ██║  ██║╚██████╔╝   ██║   ██║  ██║\n' +
            '   ╚═╝   ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚═╝  ╚═╝</pre>' +
            '<div class="subtitle">Flight Software Codebase Intelligence</div>';
        append(div);
    }

    function renderStatus(text) {
        var div = el("div", "status");
        div.innerHTML = '<span class="ok">Systems nominal.</span> ' + escHtml(text);
        append(div);
    }

    function renderSuggestions(items) {
        var box = el("div", "box cyan");
        box.innerHTML = '<div class="box-title">Try a question</div>';
        var body = el("div", "box-body");
        items.forEach(function (q, i) {
            var btn = el("button", "suggestion");
            btn.innerHTML = '<span class="num">[' + (i + 1) + ']</span>' + escHtml(q);
            btn.addEventListener("click", function () {
                if (input.disabled) return;
                dismissGlow();
                input.value = "";
                disableInput();
                sendInput(String(i + 1));
            });
            body.appendChild(btn);
        });
        box.appendChild(body);
        append(box);
    }

    function renderHint(text) {
        append(el("div", "hint", escHtml(text)));
    }

    function renderQuery(text) {
        var box = el("div", "box magenta");
        box.innerHTML =
            '<div class="box-title">Query</div>' +
            '<div class="box-body">' + escHtml(text) + '</div>';
        append(box);
    }

    function renderStreamStart() {
        var box = el("div", "box green");
        box.innerHTML = '<div class="box-title">Answer</div>';
        currentAnswer = el("div", "answer-body");
        box.appendChild(currentAnswer);
        append(box);
    }

    function renderToken(text) {
        if (!currentAnswer) return;
        currentAnswer.textContent += text;
        scrollBottom();
    }

    function renderStreamEnd(data) {
        currentAnswer = null;

        // Sources
        if (data.sources && data.sources.length > 0) {
            var box = el("div", "box cyan");
            box.innerHTML = '<div class="box-title">Sources</div>';
            var body = el("div", "box-body");

            data.sources.forEach(function (src, i) {
                var row = el("div", "source-row");

                var num = el("span", "source-num", (i + 1) + ".");

                // Score bar
                var bar = el("div", "score-bar");
                var filled = Math.round(src.score * 10);
                var level = src.score > 0.7 ? "high" : src.score > 0.4 ? "mid" : "low";
                for (var p = 0; p < 10; p++) {
                    var pip = el("div", "pip" + (p < filled ? " filled " + level : ""));
                    bar.appendChild(pip);
                }

                var cbLabel = "";
                if (src.codebase) {
                    cbLabel = el("span", "source-codebase " + src.codebase, escHtml(src.codebase));
                }

                var path = el("span", "source-path", escHtml(src.path));
                var meta = el("span", "source-meta",
                    ":" + src.start_line + "-" + src.end_line + " (" + escHtml(src.chunk_type) + ")");

                row.appendChild(num);
                row.appendChild(bar);
                if (cbLabel) row.appendChild(cbLabel);
                row.appendChild(path);
                row.appendChild(meta);
                body.appendChild(row);
            });

            box.appendChild(body);
            append(box);
        }

        // Latency
        if (data.latency_ms !== undefined) {
            var lat = el("div", "latency");
            var ms = Math.round(data.latency_ms);
            var cls, label;
            if (ms < 2000)      { cls = "fast"; label = "fast"; }
            else if (ms < 4000) { cls = "ok";   label = "ok"; }
            else                { cls = "slow"; label = "slow"; }
            lat.innerHTML =
                'Response time: <span class="' + cls + '">' + ms + 'ms</span> (' + label + ')';
            append(lat);
        }

        append(el("div", "separator"));
    }

    function renderLoading(phrase) {
        var div = el("div", "loading");
        div.id = "loading-indicator";
        div.innerHTML =
            '<div class="dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>' +
            '<span class="phrase">' + escHtml(phrase) + '</span>';
        append(div);
    }

    function removeLoading() {
        var el = document.getElementById("loading-indicator");
        if (el) el.remove();
    }

    function renderHelp(commands) {
        var box = el("div", "box yellow");
        box.innerHTML = '<div class="box-title">Commands</div>';
        var body = el("div", "box-body");
        commands.forEach(function (c) {
            var row = el("div", "help-row");
            row.innerHTML =
                '<span class="cmd">' + escHtml(c.cmd) + '</span>' +
                '<span class="desc">' + escHtml(c.desc) + '</span>';
            body.appendChild(row);
        });
        var note = el("div", "help-note",
            'Type a number <strong style="color:#d4d4d4">1-7</strong> to pick a suggested question, or type any natural language query.');
        body.appendChild(note);
        box.appendChild(body);
        append(box);
    }

    function renderError(text) {
        append(el("div", "error-msg", escHtml(text)));
    }

    function renderInfo(text) {
        append(el("div", "info-msg", escHtml(text)));
    }

    function escHtml(s) {
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    // ── Input handling ───────────────────────────────────

    input.addEventListener("keydown", function (e) {
        dismissGlow();
        if (e.key === "Enter" && !input.disabled) {
            var text = input.value.trim();
            input.value = "";
            if (!text) return;
            disableInput();
            sendInput(text);
        }
    });

    // Number hotkeys when input is not focused
    document.addEventListener("keydown", function (e) {
        if (document.activeElement === input) return;
        if (input.disabled) return;
        var n = parseInt(e.key);
        if (n >= 1 && n <= 9) {
            e.preventDefault();
            dismissGlow();
            disableInput();
            sendInput(String(n));
        }
    });

    // ── WebSocket ────────────────────────────────────────

    function connect() {
        output.innerHTML = "";
        if (splashDone) {
            append(el("div", "info-msg", "Connecting to GroundTruth backend..."));
        }
        ws = new WebSocket(WS_URL);

        ws.onopen = function () {
            output.innerHTML = "";
            input.focus();
        };

        ws.onmessage = function (event) {
            var msg;
            try { msg = JSON.parse(event.data); } catch (e) { return; }

            // During splash, buffer messages and mark backend as ready
            if (!splashDone) {
                splashReady = true;
                messageBuffer.push(msg);
                tryDismissSplash();
                return;
            }

            handleMessage(msg);
        };

        ws.onclose = function () {
            disableInput();
            append(el("div", "info-msg", "Connection lost. Reconnecting in 3s..."));
            setTimeout(connect, 3000);
        };

        ws.onerror = function (err) {
            console.error("WebSocket error:", err);
        };
    }

    function handleMessage(msg) {
        switch (msg.type) {
            case "header":
                renderHeader();
                break;
            case "status":
                renderStatus(msg.data);
                break;
            case "suggestions":
                renderSuggestions(msg.data);
                break;
            case "hint":
                renderHint(msg.data);
                break;
            case "prompt":
                enableInput();
                break;
            case "loading":
                if (msg.data) renderLoading(msg.phrase || "");
                else removeLoading();
                break;
            case "query":
                renderQuery(msg.data);
                break;
            case "stream_start":
                renderStreamStart();
                break;
            case "token":
                renderToken(msg.data);
                break;
            case "stream_end":
                renderStreamEnd(msg.data);
                break;
            case "help":
                renderHelp(msg.data);
                break;
            case "error":
                renderError(msg.data);
                break;
            case "info":
                renderInfo(msg.data);
                break;
            case "feedback_prompt":
                input.placeholder = "Type your feedback...";
                enableInput();
                break;
            case "feedback_ack":
                input.placeholder = "Ask about Adamant, cFS, or CubeDOS...";
                renderInfo(msg.data);
                break;
        }
    }

    // Keepalive
    setInterval(function () {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
        }
    }, 30000);

    showSplash();
    connect();
})();
