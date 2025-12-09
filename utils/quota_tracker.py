"""Quota tracking for TTS and translation services.

Tracks character usage per service per month to avoid exceeding free tier limits.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


# Default free tier limits (characters per month)
DEFAULT_LIMITS = {
    "google_tts": 1_000_000,  # Google Cloud TTS Standard voices
    "google_translate": 500_000,  # Google Translate API
    "deepl_free": 500_000,  # DeepL Free API
}


class QuotaTracker:
    """Tracks character usage for TTS and translation services."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize quota tracker.

        Args:
            config_path: Path to JSON config file. Defaults to ~/.bilanggen_quota.json
        """
        self.config_path = config_path or Path.home() / ".bilanggen_quota.json"
        self._data = self._load()

    def _load(self) -> dict:
        """Load quota data from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"services": {}}

    def _save(self):
        """Save quota data to file."""
        with open(self.config_path, "w") as f:
            json.dump(self._data, f, indent=2)

    def _get_current_month(self) -> str:
        """Get current month as YYYY-MM string."""
        return datetime.now().strftime("%Y-%m")

    def _ensure_service(self, service: str):
        """Ensure service entry exists and is current month."""
        current_month = self._get_current_month()

        if "services" not in self._data:
            self._data["services"] = {}

        if service not in self._data["services"]:
            self._data["services"][service] = {
                "chars_used": 0,
                "month": current_month
            }
        elif self._data["services"][service].get("month") != current_month:
            # New month - reset counter
            self._data["services"][service] = {
                "chars_used": 0,
                "month": current_month
            }

    def add_usage(self, service: str, chars: int):
        """Record character usage for a service.

        Args:
            service: Service name (e.g., 'google_tts', 'deepl_free')
            chars: Number of characters used
        """
        self._ensure_service(service)
        self._data["services"][service]["chars_used"] += chars
        self._save()

    def get_usage(self, service: str) -> int:
        """Get current month's character usage for a service.

        Args:
            service: Service name

        Returns:
            Number of characters used this month
        """
        self._ensure_service(service)
        return self._data["services"][service]["chars_used"]

    def get_limit(self, service: str) -> int:
        """Get the free tier limit for a service.

        Args:
            service: Service name

        Returns:
            Character limit (0 if unknown)
        """
        return DEFAULT_LIMITS.get(service, 0)

    def get_remaining(self, service: str) -> int:
        """Get remaining characters for free tier.

        Args:
            service: Service name

        Returns:
            Remaining characters (negative if over limit)
        """
        limit = self.get_limit(service)
        if limit == 0:
            return float("inf")  # No known limit
        return limit - self.get_usage(service)

    def get_percent_used(self, service: str) -> float:
        """Get percentage of free tier used.

        Args:
            service: Service name

        Returns:
            Percentage (0-100+)
        """
        limit = self.get_limit(service)
        if limit == 0:
            return 0.0
        return (self.get_usage(service) / limit) * 100

    def check_warning(self, service: str) -> Optional[str]:
        """Check if usage is approaching limit.

        Args:
            service: Service name

        Returns:
            Warning message if approaching/exceeding limit, None otherwise
        """
        percent = self.get_percent_used(service)
        usage = self.get_usage(service)
        limit = self.get_limit(service)

        if limit == 0:
            return None

        if percent >= 100:
            return f"WARNING: {service} quota EXCEEDED! Used {usage:,} of {limit:,} chars ({percent:.1f}%)"
        elif percent >= 95:
            return f"WARNING: {service} quota at 95%! Used {usage:,} of {limit:,} chars"
        elif percent >= 80:
            return f"Note: {service} quota at {percent:.0f}% ({usage:,}/{limit:,} chars)"

        return None

    def get_all_stats(self) -> dict:
        """Get usage stats for all services.

        Returns:
            Dict mapping service name to usage info
        """
        result = {}
        for service in self._data.get("services", {}):
            self._ensure_service(service)
            limit = self.get_limit(service)
            result[service] = {
                "chars_used": self.get_usage(service),
                "limit": limit,
                "remaining": self.get_remaining(service) if limit > 0 else None,
                "percent": self.get_percent_used(service) if limit > 0 else None,
                "month": self._data["services"][service]["month"],
            }
        return result

    def format_report(self) -> str:
        """Format a human-readable usage report.

        Returns:
            Formatted report string
        """
        stats = self.get_all_stats()
        if not stats:
            return "No usage recorded yet."

        lines = ["Quota Usage Report:", "=" * 40]

        for service, info in sorted(stats.items()):
            lines.append(f"\n{service}:")
            lines.append(f"  Used: {info['chars_used']:,} chars")

            if info['limit']:
                lines.append(f"  Limit: {info['limit']:,} chars")
                lines.append(f"  Remaining: {info['remaining']:,} chars")
                lines.append(f"  Usage: {info['percent']:.1f}%")

                # Warning indicator
                if info['percent'] >= 100:
                    lines.append(f"  STATUS: EXCEEDED!")
                elif info['percent'] >= 80:
                    lines.append(f"  STATUS: Approaching limit")
            else:
                lines.append("  Limit: Unknown/Unlimited")

            lines.append(f"  Month: {info['month']}")

        return "\n".join(lines)


# Global instance
_tracker: Optional[QuotaTracker] = None


def get_tracker() -> QuotaTracker:
    """Get global QuotaTracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = QuotaTracker()
    return _tracker


def add_tts_usage(provider: str, chars: int):
    """Convenience function to track TTS usage.

    Args:
        provider: TTS provider name (e.g., 'google_cloud', 'gtts')
        chars: Number of characters synthesized
    """
    # Map provider names to service names
    service_map = {
        "google_cloud": "google_tts",
        "gtts": "gtts",  # gtts has rate limits but no char limit
    }
    service = service_map.get(provider, provider)
    get_tracker().add_usage(service, chars)


def add_translation_usage(provider: str, chars: int):
    """Convenience function to track translation usage.

    Args:
        provider: Translation provider name
        chars: Number of characters translated
    """
    service_map = {
        "google": "google_translate",
        "deepl-free": "deepl_free",
        "deepl-pro": "deepl_pro",
        "argos": "argos",  # Local, no limits
    }
    service = service_map.get(provider, provider)

    # Only track services with limits
    if service in DEFAULT_LIMITS or service in ["google_translate", "deepl_free"]:
        get_tracker().add_usage(service, chars)
