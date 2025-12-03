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

    try:
        repo = g.get_repo(repo_name)
    except GithubException:
        return {"error": "Repository not found or private."}

    # Data Container
    metrics = {
        "repo_name": repo.full_name,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "open_issues": repo.open_issues_count,
        "avg_response_time_hours": 0,
        "avg_pr_latency_days": 0,
        # --- NEW/UPDATED METRICS HERE ---
        "total_contributors": 0,
        "bus_factor": "N/A",  # Initialize Bus Factor
        # -----------------------------
    }

    # --- METRIC 1: Response Time (Time to first comment on Issues) ---
    issues = repo.get_issues(state="closed", sort="created", direction="desc")[:20]
    response_times = []
    # ... (existing calculation logic for response_times remains the same) ...
    for issue in issues:
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

    # --- METRIC 2: Review Latency (Time to Merge/Close PRs) ---
    pulls = repo.get_pulls(state="closed", sort="created", direction="desc")[:20]
    pr_latencies = []
    # ... (existing calculation logic for pr_latencies remains the same) ...
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

    except Exception as e:
        # This can happen if statistics are still processing (GitHub 202 error)
        print(f"Warning: Could not calculate Bus Factor/Contributor stats. Error: {e}")
        metrics["total_contributors"] = "N/A"
        metrics["bus_factor"] = "N/A"

    return metrics
