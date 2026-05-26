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
            user = self.client.get_user()
            head = f"{user.login}:{branch_name}"
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head,
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

def generate_pr_body(repo_full_name: str, issue_num: int, solver_summary: str) -> str:
    return f"""# Pull Request

## Description

<!-- What and why: Describe your changes and the motivation behind them -->
<!-- Be the storyteller here — what magic did you work and why does the world need it? -->
{solver_summary}

## Related Issue

<!-- Link to the issue this PR addresses (if any). -->
<!-- Psst... linking issues helps us all stay sane. If this’s a new feature or bug fix, please create an issue first — teamwork makes the dream work! -->

- Resolve {repo_full_name}#{issue_num}

## Type of Change

<!-- Select all that apply -->

- [x] Bug fix (non-breaking change that resolves an issue — you’re a bug whisperer 🐛)
- [ ] New feature (adding shiny new toys for everyone to enjoy ✨)
- [ ] Optimization (speeding things up like a caffeinated cheetah ⚡)
- [ ] Refactor (tidying up the code closet without changing behavior 🧹)
- [ ] Documentation (making our life easier for future humans 📚)
- [ ] Other (please describe):

## ⚠️ Breaking Changes

<!-- Will this change break the existing universe? -->
<!-- If yes, please list what is breaking and what needs to be changed in the consuming applications. -->

- [x] No breaking changes (smooth sailing ⛵)
- [ ] Yes (please describe below, and brace for impact 💥)

## 🚀 Deployment & Ops

<!-- Do we need to do anything special to deploy this? -->

- [ ] New environment variables required (don't keep secrets to yourself 🤫)
- [ ] Database migrations (shifting the tectonic plates 🌍)
- [ ] Configuration changes (turning the knobs 🎛️)
- [x] None (just standard procedure)

## Testing

<!-- How did you verify your changes? Include environment, test types, and relevant configurations -->
<!-- Be the hero and tell us how you proved your code works. -->

- [ ] Unit Tests (testing bits and pieces in isolation — like mini checkups 🩺)
- [ ] Integration Tests (making sure all the parts play nice together 🤝)

**Test Environment:**

<!-- OS, tools, dependencies, or any other wizardry -->

## 🛡️ Security & Performance

- [x] I have checked for security vulnerabilities (no open doors 🚪)
- [x] I have verified performance impacts (no heavy lifting 🏋️)

## Screenshots (if applicable)

<!-- A picture is worth a thousand words — show off your handiwork! 📸 -->
<!-- Use Before/After comparisons if changing UI -->

| Before  | After   |
| ------- | ------- |
| _Image_ | _Image_ |

## Checklist

<!-- Mark all applicable items with an `x`. If unsure, shout for help! -->

- [x] Code follows style guidelines and has been self-reviewed (mirror time 🪞)
- [ ] Comments added for complex or unclear code (be the guiding light 🔦)
- [ ] Documentation updated if needed (help out future you 🙌)
- [x] No new warnings introduced; all tests pass locally (smooth sailing ⛵)
- [ ] Tests added or updated to verify changes (proof is in the pudding 🍮)
- [ ] Dependent changes merged and published (all linked up 🔗)
"""
