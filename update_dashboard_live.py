from pathlib import Path

path = Path("templates/dashboard.html")
text = path.read_text(encoding="utf-8")

animation = """
<style>
.dot {
    animation: livePulse 1.8s ease-in-out infinite;
}

@keyframes livePulse {
    0%, 100% {
        opacity: 1;
        transform: scale(1);
        box-shadow: 0 0 7px rgba(164,208,7,.65);
    }

    50% {
        opacity: .35;
        transform: scale(.82);
        box-shadow: 0 0 3px rgba(164,208,7,.25);
    }
}
</style>
"""

if "livePulse" not in text:
    text = text.replace("</head>", animation + "\n</head>")

path.write_text(text, encoding="utf-8")

print("Dashboard LIVE animation elave edildi.")
