import logging
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger(__name__)


def render_markdown(text: Optional[str]) -> str:
    if not text:
        return ""
    import html as html_module
    escaped = html_module.escape(text)
    lines = escaped.split("\n")
    result_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            if in_list:
                result_lines.append("</ul>")
                in_list = False
            result_lines.append(f"<h1 class='text-2xl font-bold mb-2'>{stripped[2:]}</h1>")
        elif stripped.startswith("## "):
            if in_list:
                result_lines.append("</ul>")
                in_list = False
            result_lines.append(f"<h2 class='text-xl font-semibold mb-2'>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            if in_list:
                result_lines.append("</ul>")
                in_list = False
            result_lines.append(f"<h3 class='text-lg font-medium mb-1'>{stripped[4:]}</h3>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                result_lines.append("<ul class='list-disc list-inside mb-2'>")
                in_list = True
            result_lines.append(f"<li>{stripped[2:]}</li>")
        elif stripped == "":
            if in_list:
                result_lines.append("</ul>")
                in_list = False
            result_lines.append("<br>")
        else:
            if in_list:
                result_lines.append("</ul>")
                in_list = False
            result_lines.append(f"<p class='mb-1'>{stripped}</p>")
    if in_list:
        result_lines.append("</ul>")
    return "\n".join(result_lines)


def format_date(value: Optional[datetime | date | str], fmt: str = "%b %d, %Y") -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            for parse_fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    value = datetime.strptime(value, parse_fmt)
                    break
                except ValueError:
                    continue
            else:
                return value
        if isinstance(value, (datetime, date)):
            return value.strftime(fmt)
        return str(value)
    except Exception:
        logger.warning("Failed to format date value: %s", value)
        return str(value)


def format_datetime(value: Optional[datetime | date | str], fmt: str = "%b %d, %Y %I:%M %p") -> str:
    return format_date(value, fmt)


def time_ago(value: Optional[datetime]) -> str:
    if value is None:
        return ""
    try:
        now = datetime.utcnow()
        if isinstance(value, str):
            for parse_fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    value = datetime.strptime(value, parse_fmt)
                    break
                except ValueError:
                    continue
            else:
                return str(value)
        diff = now - value
        seconds = int(diff.total_seconds())
        if seconds < 0:
            return "just now"
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 7:
            return f"{days}d ago"
        weeks = days // 7
        if weeks < 4:
            return f"{weeks}w ago"
        months = days // 30
        if months < 12:
            return f"{months}mo ago"
        years = days // 365
        return f"{years}y ago"
    except Exception:
        logger.warning("Failed to compute time_ago for value: %s", value)
        return ""


ROLE_DISPLAY_NAMES: dict[str, str] = {
    "super_admin": "Super Admin",
    "admin": "Admin",
    "hiring_manager": "Hiring Manager",
    "recruiter": "Recruiter",
    "interviewer": "Interviewer",
    "viewer": "Viewer",
    "candidate": "Candidate",
}


def get_role_display_name(role: Optional[str]) -> str:
    if not role:
        return "Unknown"
    return ROLE_DISPLAY_NAMES.get(role, role.replace("_", " ").title())


STAGE_COLORS: dict[str, dict[str, str]] = {
    "applied": {
        "bg": "bg-blue-100",
        "text": "text-blue-800",
        "border": "border-blue-300",
        "dot": "bg-blue-500",
    },
    "screening": {
        "bg": "bg-purple-100",
        "text": "text-purple-800",
        "border": "border-purple-300",
        "dot": "bg-purple-500",
    },
    "phone_screen": {
        "bg": "bg-indigo-100",
        "text": "text-indigo-800",
        "border": "border-indigo-300",
        "dot": "bg-indigo-500",
    },
    "interview": {
        "bg": "bg-yellow-100",
        "text": "text-yellow-800",
        "border": "border-yellow-300",
        "dot": "bg-yellow-500",
    },
    "technical_interview": {
        "bg": "bg-orange-100",
        "text": "text-orange-800",
        "border": "border-orange-300",
        "dot": "bg-orange-500",
    },
    "assessment": {
        "bg": "bg-cyan-100",
        "text": "text-cyan-800",
        "border": "border-cyan-300",
        "dot": "bg-cyan-500",
    },
    "offer": {
        "bg": "bg-green-100",
        "text": "text-green-800",
        "border": "border-green-300",
        "dot": "bg-green-500",
    },
    "hired": {
        "bg": "bg-emerald-100",
        "text": "text-emerald-800",
        "border": "border-emerald-300",
        "dot": "bg-emerald-500",
    },
    "rejected": {
        "bg": "bg-red-100",
        "text": "text-red-800",
        "border": "border-red-300",
        "dot": "bg-red-500",
    },
    "withdrawn": {
        "bg": "bg-gray-100",
        "text": "text-gray-800",
        "border": "border-gray-300",
        "dot": "bg-gray-500",
    },
    "on_hold": {
        "bg": "bg-amber-100",
        "text": "text-amber-800",
        "border": "border-amber-300",
        "dot": "bg-amber-500",
    },
}

DEFAULT_STAGE_COLOR: dict[str, str] = {
    "bg": "bg-gray-100",
    "text": "text-gray-800",
    "border": "border-gray-300",
    "dot": "bg-gray-500",
}


def get_stage_color(stage: Optional[str]) -> dict[str, str]:
    if not stage:
        return DEFAULT_STAGE_COLOR
    return STAGE_COLORS.get(stage.lower(), DEFAULT_STAGE_COLOR)


def get_stage_bg(stage: Optional[str]) -> str:
    return get_stage_color(stage)["bg"]


def get_stage_text(stage: Optional[str]) -> str:
    return get_stage_color(stage)["text"]


def get_stage_border(stage: Optional[str]) -> str:
    return get_stage_color(stage)["border"]


def get_stage_dot(stage: Optional[str]) -> str:
    return get_stage_color(stage)["dot"]


def format_stage_name(stage: Optional[str]) -> str:
    if not stage:
        return "Unknown"
    return stage.replace("_", " ").title()


STATUS_COLORS: dict[str, dict[str, str]] = {
    "open": {"bg": "bg-green-100", "text": "text-green-800"},
    "closed": {"bg": "bg-red-100", "text": "text-red-800"},
    "draft": {"bg": "bg-gray-100", "text": "text-gray-800"},
    "paused": {"bg": "bg-yellow-100", "text": "text-yellow-800"},
    "active": {"bg": "bg-blue-100", "text": "text-blue-800"},
    "archived": {"bg": "bg-gray-100", "text": "text-gray-600"},
}

DEFAULT_STATUS_COLOR: dict[str, str] = {"bg": "bg-gray-100", "text": "text-gray-800"}


def get_status_color(status: Optional[str]) -> dict[str, str]:
    if not status:
        return DEFAULT_STATUS_COLOR
    return STATUS_COLORS.get(status.lower(), DEFAULT_STATUS_COLOR)


def truncate_text(text: Optional[str], length: int = 100, suffix: str = "...") -> str:
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + suffix


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    if plural is None:
        plural = singular + "s"
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural}"


def register_template_helpers(env: "jinja2.Environment") -> None:
    env.filters["markdown"] = render_markdown
    env.filters["format_date"] = format_date
    env.filters["format_datetime"] = format_datetime
    env.filters["time_ago"] = time_ago
    env.filters["truncate_text"] = truncate_text
    env.filters["stage_name"] = format_stage_name

    env.globals["get_role_display_name"] = get_role_display_name
    env.globals["get_stage_color"] = get_stage_color
    env.globals["get_stage_bg"] = get_stage_bg
    env.globals["get_stage_text"] = get_stage_text
    env.globals["get_stage_border"] = get_stage_border
    env.globals["get_stage_dot"] = get_stage_dot
    env.globals["format_stage_name"] = format_stage_name
    env.globals["get_status_color"] = get_status_color
    env.globals["pluralize"] = pluralize
    env.globals["truncate_text"] = truncate_text