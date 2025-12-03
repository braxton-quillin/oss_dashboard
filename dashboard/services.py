import os
import statistics
from datetime import datetime, timezone
from github import Github, GithubException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_repo_health_metrics(repo_name):
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
        "avg_response_time_hours": 0,  # dt from issue to first comment
        "avg_pr_latency_days": 0,  # dt from issue to first comment
        "total_contributors": 0,  # related to 'truck factor'??
        "total_commits_last_year": 0,
    }  ##add truck factor

    # Response Time (Time to first comment on Issues)
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

    # METRIC 2: Review Latency (Time to Merge/Close PRs)
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

    # METRIC 3 & 4: Contributor Activity
    try:
        # Fetch Total Contributors
        metrics["total_contributors"] = repo.get_contributors().totalCount

        # Fetch Commit Activity (Last 52 weeks)
        commit_activity = repo.get_stats_commit_activity()

        # Calculate the total number of commits
        total_commits = sum(week.total for week in commit_activity)
        metrics["total_commits_last_year"] = total_commits

    except Exception as e:
        # Handle cases where statistics are still processing or unavailable
        print(f"Warning: Could not fetch commit statistics. Error: {e}")
        metrics["total_contributors"] = "N/A"
        metrics["total_commits_last_year"] = "N/A"

    return metrics
