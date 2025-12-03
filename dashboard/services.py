import os
import statistics
from datetime import datetime, timezone
from github import Github, GithubException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_repo_health_metrics(repo_name):
    """
    Analyzes a GitHub repository and returns health metrics.
    repo_name example: "django/django" or "torvalds/linux"
    """

    # Initialize GitHub API with token
    token = os.getenv("GITHUB_TOKEN")
    g = Github(token)

    rate_limit = g.get_rate_limit()

    try:
        rate_limit_remaining = rate_limit.resources.core.remaining
    except AttributeError:
        # Fallback for unexpected structure
        rate_limit_remaining = getattr(rate_limit.core, "remaining", 0)

    if rate_limit_remaining < 5:  # Halt if limit is nearly exhausted
        return {
            "error": f"API Rate Limit Warning: Only {rate_limit_remaining} requests remaining. Please wait one hour or provide a new token.",
            "rate_limit_remaining": rate_limit_remaining,
        }

    try:
        repo = g.get_repo(repo_name)
    except GithubException as e:
        error_msg = (
            f"Repository not found, private, or unknown GitHub error: {e.status}"
        )
        return {"error": error_msg, "rate_limit_remaining": rate_limit_remaining}

    # Data Container (Updated with all new metrics)
    metrics = {
        "repo_name": repo.full_name,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "open_issues": repo.open_issues_count,
        "avg_response_time_hours": "N/A",
        "avg_pr_latency_days": "N/A",
        "total_contributors": "N/A",
        "bus_factor": "N/A",
        "rate_limit_remaining": rate_limit_remaining,
        "last_commit_date": "N/A",
        "avg_issue_age_days": "N/A",
        "health_percentage": 0,
        "language": repo.language or "N/A",
        "license": repo.license.name if repo.license else "Unspecified",
        "bus_factor_color": "secondary",
        "response_time_color": "secondary",
        "latency_color": "secondary",
        "health_color": "secondary",
        "age_color": "secondary",
    }

    if repo.pushed_at:
        metrics["last_commit_date"] = repo.pushed_at.strftime("%b %d, %Y")

    # --- METRIC 1: Response Time (Time to first comment on Issues) ---
    issues_closed = repo.get_issues(state="closed", sort="created", direction="desc")[
        :20
    ]
    response_times = []

    for issue in issues_closed:
        if issue.pull_request:
            continue

        comments = issue.get_comments()
        if comments.totalCount > 0:
            first_comment = comments[0]
            delta = first_comment.created_at - issue.created_at
            response_times.append(delta.total_seconds())

    if response_times:
        avg_seconds = statistics.mean(response_times)
        metrics["avg_response_time_hours"] = round(avg_seconds / 3600, 2)

    issues_open = repo.get_issues(state="open", sort="created", direction="desc")
    issue_ages = []
    now = datetime.now(timezone.utc)

    for issue in issues_open:
        if issue.pull_request:
            continue
        delta = now - issue.created_at
        issue_ages.append(delta.total_seconds())

    if issue_ages:
        avg_seconds = statistics.mean(issue_ages)
        metrics["avg_issue_age_days"] = round(avg_seconds / 86400, 1)

    # --- METRIC 2: Review Latency (Time to Merge/Close PRs) ---
    pulls = repo.get_pulls(state="closed", sort="created", direction="desc")[:20]
    pr_latencies = []

    for pr in pulls:
        end_time = pr.merged_at if pr.merged else pr.closed_at

        if end_time:
            delta = end_time - pr.created_at
            pr_latencies.append(delta.total_seconds())

    if pr_latencies:
        avg_seconds = statistics.mean(pr_latencies)
        metrics["avg_pr_latency_days"] = round(avg_seconds / 86400, 2)

    # --- METRIC 3 & 4: Contributor Sustainability (Bus Factor) ---
    try:
        # Get Total Contributors
        metrics["total_contributors"] = repo.get_contributors().totalCount

        # Get weekly contributor statistics (includes additions)
        contributor_stats = repo.get_stats_contributors()

        # 1. Calculate total additions for the entire repository
        total_additions = sum(
            week.a for contributor in contributor_stats for week in contributor.weeks
        )

        # 2. Compile each contributor's total additions
        contributor_additions = []
        for contributor in contributor_stats:
            if contributor.author:
                total_contributor_additions = sum(week.a for week in contributor.weeks)
                contributor_additions.append(total_contributor_additions)

        # Sort contributions descending to find the top authors
        contributor_additions.sort(reverse=True)

        # 3. Calculate Bus Factor (minimum contributors for 50% of additions)
        target_additions = total_additions * 0.50
        cumulative_additions = 0
        bus_factor = 0

        for additions in contributor_additions:
            cumulative_additions += additions
            bus_factor += 1
            if cumulative_additions >= target_additions:
                metrics["bus_factor"] = bus_factor
                break

        # If total_additions is 0 (new repo), set to 1
        if total_additions == 0:
            metrics["bus_factor"] = 1

    except GithubException as e:
        if e.status == 202:
            metrics["bus_factor"] = "Processing..."
            metrics["total_contributors"] = "Processing..."
        else:
            # Handle other GitHubExceptions
            metrics["bus_factor"] = "N/A"
            metrics["total_contributors"] = "N/A"

    try:
        # Fetching community profile metrics
        community_profile = repo.get_community_profile()
        # The API returns an int score (e.g., 50 for 50%).
        metrics["health_percentage"] = community_profile.health_percentage or 0
    except Exception:
        metrics["health_percentage"] = (
            0  # Default to 0 if API fails or profile is missing
        )

    # 1. Bus Factor Color
    bus_factor_level = metrics["bus_factor"]
    if isinstance(bus_factor_level, int):
        if bus_factor_level < 3:
            metrics["bus_factor_color"] = "danger"  # Red (High Risk)
        elif bus_factor_level < 10:
            metrics["bus_factor_color"] = "warning"  # Yellow (Moderate Risk)
        else:
            metrics["bus_factor_color"] = "success"  # Green (Low Risk)

    # 2. Avg. Response Time Color (Hours)
    response_time_level = metrics["avg_response_time_hours"]
    if isinstance(response_time_level, (int, float)):
        if response_time_level < 24:
            metrics["response_time_color"] = "success"  # Green (Fast)
        elif response_time_level < 72:
            metrics["response_time_color"] = "warning"  # Yellow (Acceptable)
        else:
            metrics["response_time_color"] = "danger"  # Red (Slow)

    # 3. Avg. Review Latency Color (Days)
    latency_level = metrics["avg_pr_latency_days"]
    if isinstance(latency_level, (int, float)):
        if latency_level < 3:
            metrics["latency_color"] = "success"  # Green (Fast)
        elif latency_level < 7:
            metrics["latency_color"] = "warning"  # Yellow (Acceptable)
        else:
            metrics["latency_color"] = "danger"  # Red (Slow)

    # 4. Community Health Score Color (Percentage)
    health_level = metrics["health_percentage"]
    if health_level >= 80:
        metrics["health_color"] = "success"  # Green (High Score)
    elif health_level >= 50:
        metrics["health_color"] = "warning"  # Yellow (Moderate Score)
    else:
        metrics["health_color"] = "danger"  # Red (Low Score)

    # 5. Avg. Open Issue Age Color (Days)
    issue_age_level = metrics["avg_issue_age_days"]
    if isinstance(issue_age_level, (int, float)):
        if issue_age_level < 30:
            metrics["age_color"] = "success"  # Green (Young Issues)
        elif issue_age_level < 90:
            metrics["age_color"] = "warning"  # Yellow (Aging Backlog)
        else:
            metrics["age_color"] = "danger"  # Red (Stale Backlog)

    return metrics
