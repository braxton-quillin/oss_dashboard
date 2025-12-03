from django.shortcuts import render
from .services import get_repo_health_metrics


def dashboard_home(request):
    context = {}

    search_query = request.GET.get("repo")

    if search_query:
        data = get_repo_health_metrics(search_query)
        context["data"] = data
        context["search_term"] = search_query
    else:
        context["search_term"] = ""

    return render(request, "index.html", context)
