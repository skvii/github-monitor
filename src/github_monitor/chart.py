"""De visualisatie: een lijngrafiek als PNG."""

from io import BytesIO

# We gebruiken Figure (object-georiënteerd) en niet pyplot: pyplot houdt globale
# toestand bij en is niet veilig als meerdere verzoeken tegelijk een grafiek maken.
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator


def render_events_chart(data: dict, offset_minutes: int) -> bytes:
    """Teken events per minuut per type en geef de PNG terug als bytes."""
    labels = [minute[11:] for minute in data["minutes"]]  # alleen 'HH:MM' tonen

    figure = Figure(figsize=(10, 4.5))
    ax = figure.subplots()
    for event_type, values in data["series"].items():
        ax.plot(labels, values, marker="o", markersize=3, label=event_type)

    ax.set_title(f"GitHub-events per minuut (laatste {offset_minutes} min, UTC)")
    ax.set_xlabel("Minuut (UTC)")
    ax.set_ylabel("Aantal events")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))  # geen "0,5 event" op de as
    ax.legend()
    ax.grid(alpha=0.3)

    # Niet elke minuut een label op de x-as, anders wordt het onleesbaar.
    step = max(1, len(labels) // 12)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels(labels[::step], rotation=45)
    figure.tight_layout()

    buffer = BytesIO()
    figure.savefig(buffer, format="png")
    return buffer.getvalue()
