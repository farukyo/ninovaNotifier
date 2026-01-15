import io
import math

import matplotlib

# Use a non-interactive backend for server environments
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm


def generate_bell_curve(grades_data: dict) -> io.BytesIO:
    """
    Generates a bell curve visualization for the given grades.

    :param grades_data: A dictionary containing grade info for a single course.
                        Structure expected:
                        {
                            "Vize 1": { "not": "80", "detaylar": {"class_avg": "70", "std_dev": "10", ...} },
                            ...
                        }
    :return: BytesIO object containing the generated image, or None if no valid data.
    """

    valid_plots = []

    # Filter items that have necessary stats
    for exam_name, info in grades_data.items():
        details = info.get("detaylar", {})

        # User Grade
        try:
            user_score = float(str(info.get("not", "")).replace(",", "."))
        except ValueError:
            continue

        # Class Stats
        try:
            mean = float(details.get("class_avg", "").replace(",", "."))
            std_dev = float(details.get("std_dev", "").replace(",", "."))
        except ValueError:
            continue

        if std_dev <= 0:
            continue

        valid_plots.append(
            {"name": exam_name, "user_score": user_score, "mean": mean, "std_dev": std_dev}
        )

    if not valid_plots:
        return None

    # Limit to reasonable number of subplots to avoid huge images
    # Sort by name or date if available? For now, just take first 6
    valid_plots = valid_plots[:6]

    num_plots = len(valid_plots)
    cols = 1 if num_plots == 1 else 2
    rows = math.ceil(num_plots / cols)

    # Figure sizing: Width 10, Height 4 per row
    fig, axes = plt.subplots(rows, cols, figsize=(10, 4 * rows), constrained_layout=True)

    # Ensure axes is iterable even if single plot
    if num_plots == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    # Style
    plt.style.use("bmh")  # 'ggplot', 'seaborn-darkgrid', 'bmh' are good options

    for i, plot_data in enumerate(valid_plots):
        ax = axes[i]
        mu = plot_data["mean"]
        sigma = plot_data["std_dev"]
        score = plot_data["user_score"]
        title = plot_data["name"]

        # Generate X-axis points
        # Cover range [mean - 4*std, mean + 4*std]
        # But also include user score range
        start = min(mu - 4 * sigma, score - 10, 0)
        end = max(mu + 4 * sigma, score + 10, 100)
        x = np.linspace(start, end, 200)
        y = norm.pdf(x, mu, sigma)

        # Plot the bell curve
        ax.plot(x, y, label="Sınıf Dağılımı", color="#3498db", linewidth=2)
        ax.fill_between(x, y, alpha=0.2, color="#3498db")

        # Mark Mean
        ax.axvline(mu, color="#2c3e50", linestyle="--", linewidth=1, label=f"Ort: {mu}")

        # Mark User Score
        # Determine color based on position relative to mean
        score_color = "#2ecc71" if score >= mu else "#e74c3c"
        ax.axvline(score, color=score_color, linestyle="-", linewidth=2, label=f"Sen: {score}")

        # Add some text explanation
        z_score = (score - mu) / sigma

        ax.set_title(f"{title}\n(Z-Score: {z_score:.2f})", fontsize=12, fontweight="bold")
        ax.legend(loc="upper right")
        ax.set_xlabel("Not")
        ax.set_ylabel("Yoğunluk")

    # Hide unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100)
    buf.seek(0)
    plt.close(fig)

    return buf
