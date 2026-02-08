# src/app/services/chart_service.py
"""Chart generation service using matplotlib."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for server-side rendering
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

logger = logging.getLogger("data_aggregator")

CHARTS_DIR = Path(__file__).parent.parent.parent / "static" / "charts"
CLEANUP_AGE_HOURS = 24


class ChartService:
    """Service for generating and managing chart files."""

    def __init__(self):
        # Ensure charts directory exists
        CHARTS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"ChartService initialized. Charts directory: {CHARTS_DIR}")

    async def generate_fear_greed_chart(self, historical_data: list[dict[str, Any]]) -> str:
        """
        Generate Fear & Greed Index time-series chart.

        Args:
            historical_data: List of {x: timestamp_ms, y: score, rating: str}

        Returns:
            Filename of generated chart (e.g., 'fg_20260207_abc123.png')
        """
        # Generate hash for unique filename
        data_hash = self._hash_data(historical_data)
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"fg_{date_str}_{data_hash}.png"
        filepath = CHARTS_DIR / filename

        # Check if already exists (cached)
        if filepath.exists():
            logger.info(f"Chart cache hit: {filename}")
            return filename

        # Generate chart in thread pool (matplotlib is CPU-bound)
        await asyncio.to_thread(self._create_chart, historical_data, filepath)

        # Trigger async cleanup
        asyncio.create_task(self._cleanup_old_charts())

        return filename

    async def generate_bar_chart(
        self,
        data: list[dict[str, Any]],
        chart_type: str,
        title: str,
        subtitle: str = "",
    ) -> str:
        """
        Generate horizontal bar chart for rankings/comparisons.

        Args:
            data: List of {label: str, value: float, ...}
            chart_type: Type identifier (e.g., 'sector', 'trending', 'gainers')
            title: Chart title
            subtitle: Optional subtitle

        Returns:
            Filename of generated chart
        """
        # Generate hash for unique filename
        data_hash = self._hash_data(data)
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{chart_type}_{date_str}_{data_hash}.png"
        filepath = CHARTS_DIR / filename

        # Check if already exists (cached)
        if filepath.exists():
            logger.info(f"Chart cache hit: {filename}")
            return filename

        # Generate chart in thread pool
        await asyncio.to_thread(
            self._create_bar_chart, data, filepath, title, subtitle
        )

        # Trigger async cleanup
        asyncio.create_task(self._cleanup_old_charts())

        return filename

    def _create_chart(self, historical_data: list[dict[str, Any]], filepath: Path) -> None:
        """Create matplotlib chart (sync, runs in thread)."""
        # Parse data
        timestamps = [datetime.fromtimestamp(d["x"] / 1000) for d in historical_data]
        scores = [d["y"] for d in historical_data]

        current_score = scores[-1]
        current_rating = historical_data[-1]["rating"]

        # Determine current zone color
        if current_score <= 25:
            zone_color = "#DC2626"  # Red
            zone_name = "EXTREME FEAR"
        elif current_score <= 45:
            zone_color = "#F97316"  # Orange
            zone_name = "FEAR"
        elif current_score <= 55:
            zone_color = "#6B7280"  # Gray
            zone_name = "NEUTRAL"
        elif current_score <= 75:
            zone_color = "#84CC16"  # Lime
            zone_name = "GREED"
        else:
            zone_color = "#16A34A"  # Green
            zone_name = "EXTREME GREED"

        # Create figure with extra height for title/legend spacing
        fig, ax = plt.subplots(figsize=(10, 7), facecolor='white')
        ax.set_facecolor('#F9FAFB')

        # Color zones (MORE VISIBLE - increased alpha)
        ax.axhspan(0, 25, alpha=0.25, color="#DC2626", zorder=1)
        ax.axhspan(25, 45, alpha=0.20, color="#F97316", zorder=1)
        ax.axhspan(45, 55, alpha=0.15, color="#9CA3AF", zorder=1)
        ax.axhspan(55, 75, alpha=0.20, color="#84CC16", zorder=1)
        ax.axhspan(75, 100, alpha=0.25, color="#16A34A", zorder=1)

        # Plot area chart with dynamic color
        ax.fill_between(timestamps, scores, alpha=0.4, color=zone_color, zorder=2)
        ax.plot(timestamps, scores, linewidth=3, color=zone_color, zorder=3)

        # HIGHLIGHT CURRENT POINT (stop-the-scroll element)
        ax.scatter(
            [timestamps[-1]], [current_score],
            s=400, color=zone_color, edgecolors='white',
            linewidths=4, zorder=10, marker='o'
        )

        # Annotate current score with large text
        ax.annotate(
            f'{current_score:.1f}',
            xy=(timestamps[-1], current_score),
            xytext=(10, 15), textcoords='offset points',
            fontsize=18, fontweight='bold', color=zone_color,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor=zone_color, linewidth=2),
            zorder=11
        )

        # Title and subtitle using figure-level suptitle
        title_text = f"Market Sentiment: {zone_name} ({current_score:.1f})"
        date_range = f"{timestamps[0].strftime('%b %d')} - {timestamps[-1].strftime('%b %d, %Y')}"

        fig.suptitle(title_text, fontsize=16, fontweight='bold', color=zone_color, y=0.98)
        fig.text(0.5, 0.94, date_range, ha='center', fontsize=11, color='#6B7280', style='italic')

        # Clean axis labels
        ax.set_ylabel("FEAR ← | → GREED", fontsize=13, fontweight='bold', color='#374151')
        ax.set_xlabel("")  # Remove x-label, dates are self-explanatory
        ax.set_ylim(0, 100)

        # Grid - horizontal only, thicker at zone boundaries
        ax.grid(True, axis='y', alpha=0.3, linestyle='-', linewidth=0.5, color='#D1D5DB')
        for zone_line in [25, 45, 55, 75]:
            ax.axhline(y=zone_line, color='#9CA3AF', linewidth=1.5, alpha=0.5, linestyle='--', zorder=2)

        # Date formatting - larger font for recent dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=21))  # Every 3 weeks
        plt.setp(ax.xaxis.get_majorticklabels(), fontsize=10, fontweight='500')
        plt.setp(ax.yaxis.get_majorticklabels(), fontsize=10)

        # Remove top and right spines for cleaner look
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#D1D5DB')
        ax.spines['bottom'].set_color('#D1D5DB')

        # Legend - compact, outside plot area
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#DC2626", alpha=0.4, label="Extreme Fear"),
            Patch(facecolor="#F97316", alpha=0.4, label="Fear"),
            Patch(facecolor="#9CA3AF", alpha=0.4, label="Neutral"),
            Patch(facecolor="#84CC16", alpha=0.4, label="Greed"),
            Patch(facecolor="#16A34A", alpha=0.4, label="Extreme Greed"),
        ]
        ax.legend(
            handles=legend_elements,
            loc='upper center',
            bbox_to_anchor=(0.5, -0.08),
            ncol=5,
            fontsize=9,
            frameon=False,
            handlelength=1.5
        )

        # Automatic layout with padding for proper spacing
        plt.tight_layout(pad=3.0, rect=[0, 0.03, 1, 0.92])

        # Save with higher DPI (no bbox_inches='tight' to preserve spacing)
        plt.savefig(filepath, dpi=120, facecolor='white')
        plt.close(fig)

        logger.info(f"Generated chart: {filepath.name}")

    def _create_bar_chart(
        self,
        data: list[dict[str, Any]],
        filepath: Path,
        title: str,
        subtitle: str,
    ) -> None:
        """Create horizontal bar chart (sync, runs in thread)."""
        # Extract labels and values
        labels = [item.get("label", "") for item in data]
        values = [item.get("value", 0) for item in data]

        # Determine colors based on positive/negative values
        colors = []
        for val in values:
            if val >= 5:
                colors.append("#16A34A")  # Green (strong positive)
            elif val >= 0:
                colors.append("#84CC16")  # Lime (weak positive)
            elif val >= -5:
                colors.append("#F97316")  # Orange (weak negative)
            else:
                colors.append("#DC2626")  # Red (strong negative)

        # Create figure with extra size for labels and title spacing
        fig, ax = plt.subplots(figsize=(11, 9), facecolor='white')
        ax.set_facecolor('#F9FAFB')

        # Create horizontal bars
        y_pos = range(len(labels))
        bars = ax.barh(y_pos, values, color=colors, alpha=0.8, height=0.7)

        # Add value labels on bars
        for i, (bar, val) in enumerate(zip(bars, values)):
            width = bar.get_width()
            label_x = width + (0.5 if width >= 0 else -0.5)
            ax.text(
                label_x, bar.get_y() + bar.get_height() / 2,
                f'{val:+.1f}%' if '%' in title else f'{int(val)}',
                ha='left' if width >= 0 else 'right',
                va='center',
                fontsize=10,
                fontweight='bold',
                color=colors[i]
            )

        # Set labels
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=11)
        ax.set_xlabel("Change (%)" if '%' in title else "Count", fontsize=12, fontweight='bold')

        # Title and subtitle using figure-level positioning
        fig.suptitle(title, fontsize=16, fontweight='bold', color='#111827', y=0.98)
        if subtitle:
            fig.text(0.5, 0.94, subtitle, ha='center', fontsize=11, color='#6B7280', style='italic')

        # Grid
        ax.grid(True, axis='x', alpha=0.3, linestyle='-', linewidth=0.5, color='#D1D5DB')
        ax.axvline(x=0, color='#374151', linewidth=1.5, alpha=0.8)

        # Remove spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#D1D5DB')

        # Automatic layout with padding for proper spacing
        plt.tight_layout(pad=3.0, rect=[0, 0, 1, 0.92])

        # Save (no bbox_inches='tight' to preserve spacing)
        plt.savefig(filepath, dpi=120, facecolor='white')
        plt.close(fig)

        logger.info(f"Generated bar chart: {filepath.name}")

    def _hash_data(self, data: list[dict[str, Any]]) -> str:
        """Generate short hash of data for filename uniqueness."""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()[:8]

    async def _cleanup_old_charts(self) -> None:
        """Remove charts older than CLEANUP_AGE_HOURS."""
        try:
            cutoff = datetime.now() - timedelta(hours=CLEANUP_AGE_HOURS)
            deleted = 0

            for filepath in CHARTS_DIR.glob("*.png"):
                if filepath.stat().st_mtime < cutoff.timestamp():
                    filepath.unlink()
                    deleted += 1

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old chart(s)")
        except Exception as e:
            logger.warning(f"Chart cleanup error: {e}")


# Singleton instance
chart_service = ChartService()
