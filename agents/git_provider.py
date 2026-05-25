import abc

class GitProvider(abc.ABC):
    @abc.abstractmethod
    def fetch_issue_details(self, repo_full_name: str, issue_number: int) -> str:
        pass

    @abc.abstractmethod
    def create_pull_request(self, repo_full_name: str, branch_name: str, title: str, body: str) -> str:
        pass

class GitHubProvider(GitProvider):
    def __init__(self, token: str):
        from github import Github
        self.client = Github(token)

    def fetch_issue_details(self, repo_full_name: str, issue_number: int) -> str:
        try:
            repo = self.client.get_repo(repo_full_name)
            issue = repo.get_issue(number=issue_number)
            return f"Title: {issue.title}\n\nBody:\n{issue.body}"
        except Exception as e:
            return f"Failed to fetch issue: {str(e)}"

    def create_pull_request(self, repo_full_name: str, branch_name: str, title: str, body: str) -> str:
        try:
            repo = self.client.get_repo(repo_full_name)
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=repo.default_branch
            )
            return f"Pull Request Created: {pr.html_url}"
        except Exception as e:
            return f"Failed to create PR: {str(e)}"

class GitLabProvider(GitProvider):
    def __init__(self, token: str):
        import gitlab
        self.client = gitlab.Gitlab(private_token=token)

    def fetch_issue_details(self, repo_full_name: str, issue_number: int) -> str:
        try:
            project = self.client.projects.get(repo_full_name)
            issue = project.issues.get(issue_iid=issue_number)
            return f"Title: {issue.title}\n\nBody:\n{issue.description}"
        except Exception as e:
            return f"Failed to fetch issue: {str(e)}"

    def create_pull_request(self, repo_full_name: str, branch_name: str, title: str, body: str) -> str:
        try:
            project = self.client.projects.get(repo_full_name)
            mr = project.mergerequests.create({
                'source_branch': branch_name,
                'target_branch': project.default_branch,
                'title': title,
                'description': body
            })
            return f"Created Merge Request: {mr.web_url}"
        except Exception as e:
            return f"Failed to create MR: {str(e)}"

class BitbucketProvider(GitProvider):
    def __init__(self, token: str):
        import httpx
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }
        self.base_url = "https://api.bitbucket.org/2.0"

    def fetch_issue_details(self, repo_full_name: str, issue_number: int) -> str:
        import httpx
        try:
            url = f"{self.base_url}/repositories/{repo_full_name}/issues/{issue_number}"
            resp = httpx.get(url, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()
            return f"Title: {data.get('title')}\n\nBody:\n{data.get('content', {}).get('raw', '')}"
        except Exception as e:
            return f"Failed to fetch issue: {str(e)}"

    def create_pull_request(self, repo_full_name: str, branch_name: str, title: str, body: str) -> str:
        import httpx
        try:
            url = f"{self.base_url}/repositories/{repo_full_name}/pullrequests"
            
            # Fetch repo to get default branch
            repo_resp = httpx.get(f"{self.base_url}/repositories/{repo_full_name}", headers=self.headers)
            repo_resp.raise_for_status()
            default_branch = repo_resp.json().get('mainbranch', {}).get('name', 'master')

            payload = {
                "title": title,
                "description": body,
                "source": {
                    "branch": {
                        "name": branch_name
                    }
                },
                "destination": {
                    "branch": {
                        "name": default_branch
                    }
                }
            }
            resp = httpx.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return f"Created Pull Request: {resp.json().get('links', {}).get('html', {}).get('href', 'Unknown URL')}"
        except Exception as e:
            return f"Failed to create PR: {str(e)}"

def get_git_provider(repo_url: str, token: str) -> GitProvider:
    if "gitlab.com" in repo_url:
        return GitLabProvider(token)
    elif "bitbucket.org" in repo_url:
        return BitbucketProvider(token)
    else:
        # Default to GitHub
        return GitHubProvider(token)
