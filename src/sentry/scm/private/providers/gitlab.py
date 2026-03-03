import datetime
import functools
from typing import Any

from sentry.integrations.gitlab.client import GitLabApiClient
from sentry.scm.errors import SCMProviderException
from sentry.scm.types import (
    ActionResult,
    Author,
    BranchName,
    BuildConclusion,
    BuildStatus,
    CheckRun,
    CheckRunOutput,
    Comment,
    Commit,
    CommitAuthor,
    CommitSHA,
    FileContent,
    GitBlob,
    GitCommitObject,
    GitRef,
    GitTree,
    InputTreeEntry,
    PaginatedActionResult,
    PaginatedResponseMeta,
    PaginationParams,
    PullRequest,
    PullRequestBranch,
    PullRequestCommit,
    PullRequestFile,
    PullRequestState,
    Reaction,
    ReactionResult,
    Referrer,
    Repository,
    RequestOptions,
    ResourceId,
    Review,
    ReviewComment,
    ReviewCommentInput,
    ReviewEvent,
    ReviewSide,
)
from sentry.shared_integrations.exceptions import ApiError

# TODO: Rate-limits are dynamic per org. Some will have higher limits. We need to dynamically
#       configure the shared pool. The absolute allocation amount for explicit referrers can
#       remain unchanged.
REFERRER_ALLOCATION: dict[Referrer, int] = {"shared": 4500, "emerge": 500}

# Placeholder pagination meta until the GitLab client supports pagination.
_DEFAULT_PAGINATED_META: PaginatedResponseMeta = PaginatedResponseMeta(next_cursor=None)

REACTION_MAPPING: list[tuple[Reaction, str]] = [
    ("+1", "thumbsup"),
    ("-1", "thumbsdown"),
    ("laugh", "laughing"),
    ("confused", "confused"),
    ("heart", "heart"),
    ("hooray", "tada"),
    ("rocket", "rocket"),
    ("eyes", "eyes"),
]

AWARD_NAME_BY_REACTION: dict[Reaction, str] = {
    reaction: award for reaction, award in REACTION_MAPPING
}

REACTION_BY_AWARD_NAME: dict[str, Reaction] = {
    award: reaction for reaction, award in REACTION_MAPPING
}


def catch_provider_exception(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ApiError as e:
            raise SCMProviderException(str(e)) from e

    return wrapper


class GitLabProvider:
    def __init__(self, client: GitLabApiClient, repository: Repository) -> None:
        self.client = client
        self.repository = repository
        external_id = repository["external_id"]
        assert external_id is not None
        prefix = "gitlab.com:"
        assert external_id.startswith(prefix)
        self._repo_id = external_id[len(prefix) :]

    def is_rate_limited(self, organization_id: int, referrer: Referrer) -> bool:
        from sentry.scm.helpers import is_rate_limited_with_allocation_policy

        return is_rate_limited_with_allocation_policy(
            organization_id,
            referrer,
            provider="gitlab",
            window=3600,
            allocation_policy=REFERRER_ALLOCATION,
        )

    # @todo Factorize mapping from raw to return types

    # @todo Move down to match GitHub provider
    @catch_provider_exception
    def get_pull_request(
        self,
        pull_request_id: str,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[PullRequest]:
        raw = self.client.get_merge_request(self._repo_id, pull_request_id)
        return ActionResult(
            data=PullRequest(
                id=raw["id"],
                number=raw["iid"],
                title=raw["title"],
                body=raw["description"] or None,
                state="open" if raw["state"] == "opened" else "closed",
                base=PullRequestBranch(ref=raw["target_branch"], sha=None),
                head=PullRequestBranch(
                    ref=raw["source_branch"],
                    sha=raw["sha"],
                ),
                merged=raw["merged_at"] is not None,
                html_url=raw["web_url"],
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def get_issue_comments(
        self,
        issue_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[Comment]:
        raw = self.client.get_issue_notes(self._repo_id, issue_id)
        return PaginatedActionResult(
            data=[
                Comment(
                    id=note["id"],
                    body=note["body"],
                    author=Author(id=note["author"]["id"], username=note["author"]["username"]),
                )
                for note in raw
            ],
            type="gitlab",
            raw=raw,
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def create_issue_comment(self, issue_id: str, body: str) -> ActionResult[Comment]:
        raw = self.client.create_issue_note(self._repo_id, issue_id, {"body": body})
        return ActionResult(
            data=Comment(
                id=raw["id"],
                body=raw["body"],
                author=Author(id=raw["author"]["id"], username=raw["author"]["username"]),
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def delete_issue_comment(self, issue_id: str, comment_id: str) -> None:
        self.client.delete_issue_note(self._repo_id, issue_id, comment_id)

    @catch_provider_exception
    def get_pull_request_comments(
        self,
        pull_request_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[Comment]:
        raw = self.client.get_merge_request_notes(self._repo_id, pull_request_id)
        return PaginatedActionResult(
            data=[
                Comment(
                    id=note["id"],
                    body=note["body"],
                    author=Author(id=note["author"]["id"], username=note["author"]["username"]),
                )
                for note in raw
            ],
            type="gitlab",
            raw=raw,
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def create_pull_request_comment(self, pull_request_id: str, body: str) -> ActionResult[Comment]:
        raw = self.client.create_merge_request_note(self._repo_id, pull_request_id, {"body": body})
        return ActionResult(
            data=Comment(
                id=raw["id"],
                body=raw["body"],
                author=Author(id=raw["author"]["id"], username=raw["author"]["username"]),
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def delete_pull_request_comment(self, pull_request_id: str, comment_id: str) -> None:
        self.client.delete_merge_request_note(self._repo_id, pull_request_id, comment_id)

    @catch_provider_exception
    def get_issue_comment_reactions(
        self,
        issue_id: str,
        comment_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[ReactionResult]:
        raw = self.client.get_issue_note_awards(self._repo_id, issue_id, comment_id)
        return PaginatedActionResult(
            data=[
                ReactionResult(
                    id=award["id"],
                    content=REACTION_BY_AWARD_NAME[award["name"]],
                    author=Author(id=award["user"]["id"], username=award["user"]["username"]),
                )
                for award in raw
                if award["name"] in REACTION_BY_AWARD_NAME
            ],
            type="gitlab",
            raw=raw,
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def create_issue_comment_reaction(
        self, issue_id: str, comment_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        raw = self.client.create_issue_note_award(
            self._repo_id, issue_id, comment_id, AWARD_NAME_BY_REACTION[reaction]
        )
        return ActionResult(
            data=ReactionResult(
                id=raw["id"],
                content=reaction,
                author=Author(id=raw["user"]["id"], username=raw["user"]["username"]),
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def delete_issue_comment_reaction(
        self, issue_id: str, comment_id: str, reaction_id: str
    ) -> None:
        self.client.delete_issue_note_award(self._repo_id, issue_id, comment_id, reaction_id)

    @catch_provider_exception
    def get_pull_request_comment_reactions(
        self,
        pull_request_id: str,
        comment_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[ReactionResult]:
        pull_request_id = "1"  # @todo GitLab needs the MR ID to get note awards
        raw = self.client.get_merge_request_note_awards(self._repo_id, pull_request_id, comment_id)
        return PaginatedActionResult(
            data=[
                ReactionResult(
                    id=award["id"],
                    content=REACTION_BY_AWARD_NAME[award["name"]],
                    author=Author(id=award["user"]["id"], username=award["user"]["username"]),
                )
                for award in raw
                if award["name"] in REACTION_BY_AWARD_NAME
            ],
            type="gitlab",
            raw=raw,
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def create_pull_request_comment_reaction(
        self, pull_request_id: str, comment_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        pull_request_id = "1"  # @todo GitLab needs the MR ID to create a note award
        raw = self.client.create_merge_request_note_award(
            self._repo_id, pull_request_id, comment_id, AWARD_NAME_BY_REACTION[reaction]
        )
        return ActionResult(
            data=ReactionResult(
                id=raw["id"],
                content=reaction,
                author=Author(id=raw["user"]["id"], username=raw["user"]["username"]),
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def delete_pull_request_comment_reaction(
        self, pull_request_id: str, comment_id: str, reaction_id: str
    ) -> None:
        self.client.delete_merge_request_note_award(
            self._repo_id, pull_request_id, comment_id, reaction_id
        )

    @catch_provider_exception
    def get_issue_reactions(
        self,
        issue_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[ReactionResult]:
        raw = self.client.get_issue_awards(self._repo_id, issue_id)
        return PaginatedActionResult(
            data=[
                ReactionResult(
                    id=award["id"],
                    content=REACTION_BY_AWARD_NAME[award["name"]],
                    author=Author(id=award["user"]["id"], username=award["user"]["username"]),
                )
                for award in raw
                if award["name"] in REACTION_BY_AWARD_NAME
            ],
            type="gitlab",
            raw=raw,
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def create_issue_reaction(
        self, issue_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        raw = self.client.create_issue_award(
            self._repo_id, issue_id, AWARD_NAME_BY_REACTION[reaction]
        )
        return ActionResult(
            data=ReactionResult(
                id=raw["id"],
                content=reaction,
                author=Author(id=raw["user"]["id"], username=raw["user"]["username"]),
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def delete_issue_reaction(self, issue_id: str, reaction_id: str) -> None:
        self.client.delete_issue_award(self._repo_id, issue_id, reaction_id)

    @catch_provider_exception
    def get_pull_request_reactions(
        self,
        pull_request_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[ReactionResult]:
        raw = self.client.get_merge_request_awards(self._repo_id, pull_request_id)
        return PaginatedActionResult(
            data=[
                ReactionResult(
                    id=award["id"],
                    content=REACTION_BY_AWARD_NAME[award["name"]],
                    author=Author(id=award["user"]["id"], username=award["user"]["username"]),
                )
                for award in raw
                if award["name"] in REACTION_BY_AWARD_NAME
            ],
            type="gitlab",
            raw=raw,
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def create_pull_request_reaction(
        self, pull_request_id: str, reaction: Reaction
    ) -> ActionResult[ReactionResult]:
        raw = self.client.create_merge_request_award(
            self._repo_id, pull_request_id, AWARD_NAME_BY_REACTION[reaction]
        )
        return ActionResult(
            data=ReactionResult(
                id=raw["id"],
                content=reaction,
                author=Author(id=raw["user"]["id"], username=raw["user"]["username"]),
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def delete_pull_request_reaction(self, pull_request_id: str, reaction_id: str) -> None:
        self.client.delete_merge_request_award(self._repo_id, pull_request_id, reaction_id)

    @catch_provider_exception
    def get_branch(
        self,
        branch: BranchName,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[GitRef]:
        raw = self.client.get_branch(self._repo_id, branch)
        return ActionResult(
            data=GitRef(ref=raw["name"], sha=raw["commit"]["id"]),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def create_branch(self, branch: BranchName, sha: CommitSHA) -> ActionResult[GitRef]:
        raw = self.client.create_branch(self._repo_id, branch, sha)
        return ActionResult(
            data=GitRef(ref=raw["name"], sha=raw["commit"]["id"]),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def update_branch(self, branch: BranchName, sha: CommitSHA, force: bool = False) -> None:
        raise NotImplementedError("Updating a branch is not supported by the GitLab API")

    @catch_provider_exception
    def create_git_blob(self, content: str, encoding: str) -> ActionResult[GitBlob]:
        raise NotImplementedError("create_git_blob")

    @catch_provider_exception
    def get_file_content(
        self,
        path: str,
        ref: str | None = None,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[FileContent]:
        raise NotImplementedError("get_file_content")

    @catch_provider_exception
    def get_commit(
        self,
        sha: CommitSHA,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[Commit]:
        raise NotImplementedError("get_commit")

    @catch_provider_exception
    def get_commits(
        self,
        sha: CommitSHA | None = None,
        path: str | None = None,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[Commit]:
        raw_commits = self.client.get_last_commits(self._repo_id, end_sha=sha)
        return PaginatedActionResult(
            data=[map_commit(c) for c in raw_commits],
            type="gitlab",
            raw={"items": raw_commits},
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def compare_commits(
        self,
        start_sha: CommitSHA,
        end_sha: CommitSHA,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[Commit]:
        raise NotImplementedError("compare_commits")

    @catch_provider_exception
    def get_tree(
        self,
        tree_sha: CommitSHA,
        recursive: bool = True,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[GitTree]:
        raise NotImplementedError("get_tree")

    @catch_provider_exception
    def get_git_commit(
        self,
        sha: CommitSHA,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[GitCommitObject]:
        raise NotImplementedError("get_git_commit")

    @catch_provider_exception
    def create_git_tree(
        self,
        tree: list[InputTreeEntry],
        base_tree: CommitSHA | None = None,
    ) -> ActionResult[GitTree]:
        raise NotImplementedError("create_git_tree")

    @catch_provider_exception
    def create_git_commit(
        self,
        message: str,
        tree_sha: CommitSHA,
        parent_shas: list[CommitSHA],
    ) -> ActionResult[GitCommitObject]:
        raise NotImplementedError("create_git_commit")

    @catch_provider_exception
    def get_pull_request_files(
        self,
        pull_request_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[PullRequestFile]:
        raise NotImplementedError("get_pull_request_files")

    @catch_provider_exception
    def get_pull_request_commits(
        self,
        pull_request_id: str,
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[PullRequestCommit]:
        raise NotImplementedError("get_pull_request_commits")

    @catch_provider_exception
    def get_pull_request_diff(
        self,
        pull_request_id: str,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[str]:
        raise NotImplementedError("get_pull_request_diff")

    @catch_provider_exception
    def get_pull_requests(
        self,
        state: PullRequestState | None = "open",  # @todo
        head: BranchName | None = None,  # @todo
        pagination: PaginationParams | None = None,
        request_options: RequestOptions | None = None,
    ) -> PaginatedActionResult[PullRequest]:
        raw = self.client.get_merge_requests(self._repo_id)
        return PaginatedActionResult(
            data=[
                PullRequest(
                    id=mr["id"],
                    number=mr["iid"],
                    title=mr["title"],
                    body=mr["description"] or None,
                    state="open" if mr["state"] == "opened" else "closed",
                    base=PullRequestBranch(ref=mr["target_branch"], sha=None),
                    head=PullRequestBranch(
                        ref=mr["source_branch"],
                        sha=mr["sha"],
                    ),
                    merged=mr["merged_at"] is not None,
                    html_url=mr["web_url"],
                )
                for mr in raw
            ],
            type="gitlab",
            raw=raw,
            meta=_DEFAULT_PAGINATED_META,
        )

    @catch_provider_exception
    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False,
    ) -> ActionResult[PullRequest]:
        data = {
            "title": title,
            "description": body,
            "source_branch": head,
            "target_branch": base,
            # GitLab doesn't have a concept of draft PRs
        }
        raw = self.client.create_merge_request(self._repo_id, data)
        return ActionResult(
            data=PullRequest(
                id=raw["id"],
                number=raw["iid"],
                title=raw["title"],
                body=raw["description"] or None,
                state="open" if raw["state"] == "opened" else "closed",
                base=PullRequestBranch(ref=raw["target_branch"], sha=None),
                head=PullRequestBranch(
                    ref=raw["source_branch"],
                    sha=raw["sha"],
                ),
                merged=raw["merged_at"] is not None,
                html_url=raw["web_url"],
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def update_pull_request(
        self,
        pull_request_id: str,
        title: str | None = None,
        body: str | None = None,
        state: PullRequestState | None = None,
    ) -> ActionResult[PullRequest]:
        data = {}
        if title is not None:
            data["title"] = title
        if body is not None:
            data["description"] = body
        if state is not None:
            if state == "open":
                data["state_event"] = "reopen"
            elif state == "closed":
                data["state_event"] = "close"
            else:
                raise ValueError("Invalid state value")
        raw = self.client.update_merge_request(self._repo_id, pull_request_id, data)
        return ActionResult(
            data=PullRequest(
                id=raw["id"],
                number=raw["iid"],
                title=raw["title"],
                body=raw["description"] or None,
                state="open" if raw["state"] == "opened" else "closed",
                base=PullRequestBranch(ref=raw["target_branch"], sha=None),
                head=PullRequestBranch(
                    ref=raw["source_branch"],
                    sha=raw["sha"],
                ),
                merged=raw["merged_at"] is not None,
                html_url=raw["web_url"],
            ),
            type="gitlab",
            raw=raw,
            meta={},
        )

    @catch_provider_exception
    def request_review(self, pull_request_id: str, reviewers: list[str]) -> None:
        raise NotImplementedError("request_review")

    @catch_provider_exception
    def create_review_comment_file(
        self,
        pull_request_id: str,
        commit_id: CommitSHA,
        body: str,
        path: str,
        side: ReviewSide,
    ) -> ActionResult[ReviewComment]:
        raise NotImplementedError("create_review_comment_file")

    @catch_provider_exception
    def create_review_comment_line(
        self,
        pull_request_id: str,
        commit_id: CommitSHA,
        body: str,
        path: str,
        line: int,
        side: ReviewSide,
    ) -> ActionResult[ReviewComment]:
        raise NotImplementedError("create_review_comment_line")

    @catch_provider_exception
    def create_review_comment_multiline(
        self,
        pull_request_id: str,
        commit_id: CommitSHA,
        body: str,
        path: str,
        start_line: int,
        start_side: ReviewSide,
        end_line: int,
        end_side: ReviewSide,
    ) -> ActionResult[ReviewComment]:
        raise NotImplementedError("create_review_comment_multiline")

    @catch_provider_exception
    def create_review_comment_reply(
        self,
        pull_request_id: str,
        body: str,
        comment_id: str,
    ) -> ActionResult[ReviewComment]:
        raise NotImplementedError("create_review_comment_reply")

    @catch_provider_exception
    def create_review(
        self,
        pull_request_id: str,
        commit_sha: CommitSHA,
        event: ReviewEvent,
        comments: list[ReviewCommentInput],
        body: str | None = None,
    ) -> ActionResult[Review]:
        raise NotImplementedError("create_review")

    @catch_provider_exception
    def create_check_run(
        self,
        name: str,
        head_sha: CommitSHA,
        status: BuildStatus | None = None,
        conclusion: BuildConclusion | None = None,
        external_id: str | None = None,
        started_at: str | None = None,
        completed_at: str | None = None,
        output: CheckRunOutput | None = None,
    ) -> ActionResult[CheckRun]:
        raise NotImplementedError("create_check_run")

    @catch_provider_exception
    def get_check_run(
        self,
        check_run_id: ResourceId,
        request_options: RequestOptions | None = None,
    ) -> ActionResult[CheckRun]:
        raise NotImplementedError("get_check_run")

    @catch_provider_exception
    def update_check_run(
        self,
        check_run_id: ResourceId,
        status: BuildStatus | None = None,
        conclusion: BuildConclusion | None = None,
        output: CheckRunOutput | None = None,
    ) -> ActionResult[CheckRun]:
        raise NotImplementedError("update_check_run")

    @catch_provider_exception
    def minimize_comment(self, comment_node_id: str, reason: str) -> None:
        raise NotImplementedError("minimize_comment")

    @catch_provider_exception
    def resolve_review_thread(self, thread_node_id: str) -> None:
        raise NotImplementedError("resolve_review_thread")


def map_commit(raw: dict[str, Any]) -> Commit:
    return Commit(
        id=raw["id"],
        message=raw["message"],
        author=CommitAuthor(
            name=raw["author_name"],
            email=raw["author_email"],
            date=datetime.datetime.fromisoformat(raw["created_at"]),
        ),
        files=None,
    )
