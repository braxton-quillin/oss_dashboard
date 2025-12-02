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
    token = os.getenv("GITHUB_TOKEN")
    g = Github(token)

    try:
        repo = g.get_repo(repo_name)
    except GithubException:
        return {"error": "Repository not found or private."}

    metrics = {
        "repo_name": repo.full_name,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "open_issues": repo.open_issues_count,
        "avg_response_time_hours": 0,
        "avg_pr_latency_days": 0,
    }

    # METRIC 1: Response Time
    # analyze the last 20 closed issues to get a recent snapshot
    issues = repo.get_issues(state="closed", sort="created", direction="desc")[:20]
    response_times = []

    for issue in issues:
        # Skip Pull Requests (GitHub API treats PRs as Issues sometimes)
        if issue.pull_request:
            continue

        comments = issue.get_comments()
        if comments.totalCount > 0:
            # Get the first comment
            first_comment = comments[0]

            # Calculate delta: First Comment Time - Issue Creation Time
            delta = first_comment.created_at - issue.created_at
            response_times.append(delta.total_seconds())

    if response_times:
        avg_seconds = statistics.mean(response_times)
        metrics["avg_response_time_hours"] = round(avg_seconds / 3600, 2)

    # METRIC 2: Review Latency
    # analyze the last 20 closed PRs
    pulls = repo.get_pulls(state="closed", sort="created", direction="desc")[:20]
    pr_latencies = []

    for pr in pulls:
        # Calculate delta: Closed/Merged Time - PR Creation Time
        end_time = pr.merged_at if pr.merged else pr.closed_at

        if end_time:
            delta = end_time - pr.created_at
            pr_latencies.append(delta.total_seconds())

    if pr_latencies:
        avg_seconds = statistics.mean(pr_latencies)
        metrics["avg_pr_latency_days"] = round(avg_seconds / 86400, 2)

    return metrics
