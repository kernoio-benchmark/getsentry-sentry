from datetime import datetime
from typing import Any, Literal

import pydantic

from ..types import (
    BuildConclusion,
    BuildStatus,
    FileStatus,
    ProviderName,
    Reaction,
    ResourceId,
    ReviewSide,
    TreeEntryMode,
    TreeEntryType,
)


class Author(pydantic.BaseModel):
    id: str
    username: str


class Comment(pydantic.BaseModel):
    id: str
    body: str | None
    author: Author | None


class ReactionResult(pydantic.BaseModel):
    id: str
    content: Reaction
    author: Author | None


class PullRequestBranch(pydantic.BaseModel):
    sha: str | None
    ref: str


class PullRequest(pydantic.BaseModel):
    id: ResourceId
    number: str
    title: str
    body: str | None
    state: Literal["open", "closed"]
    merged: bool
    html_url: str
    head: PullRequestBranch
    base: PullRequestBranch


class ActionResult[T](pydantic.BaseModel):
    data: T
    type: ProviderName
    raw: dict[str, Any]


class Repository(pydantic.BaseModel):
    integration_id: int
    name: str
    organization_id: int
    status: int
    external_id: str | None


class GitRef(pydantic.BaseModel):
    ref: str
    sha: str


class GitBlob(pydantic.BaseModel):
    sha: str


class FileContent(pydantic.BaseModel):
    path: str
    sha: str
    content: str  # base64-encoded
    encoding: str
    size: int


class CommitAuthor(pydantic.BaseModel):
    name: str
    email: str
    date: datetime | None


class CommitFile(pydantic.BaseModel):
    filename: str
    status: FileStatus
    patch: str | None


class Commit(pydantic.BaseModel):
    id: str
    message: str
    author: CommitAuthor | None
    files: list[CommitFile] | None


class CommitComparison(pydantic.BaseModel):
    ahead_by: int
    behind_by: int
    commits: list[Commit]


class TreeEntry(pydantic.BaseModel):
    path: str
    mode: TreeEntryMode
    type: TreeEntryType
    sha: str
    size: int | None


class InputTreeEntry(pydantic.BaseModel):
    path: str
    mode: TreeEntryMode
    type: TreeEntryType
    sha: str | None


class GitTree(pydantic.BaseModel):
    sha: str
    tree: list[TreeEntry]
    truncated: bool


class GitCommitTree(pydantic.BaseModel):
    sha: str


class GitCommitObject(pydantic.BaseModel):
    sha: str
    tree: GitCommitTree
    message: str


class PullRequestFile(pydantic.BaseModel):
    filename: str
    status: FileStatus
    patch: str | None
    changes: int
    sha: str
    previous_filename: str | None


class PullRequestCommit(pydantic.BaseModel):
    sha: str
    message: str
    author: CommitAuthor | None


class ReviewCommentInput(pydantic.BaseModel):
    path: str
    body: str
    line: int | None = None
    side: ReviewSide | None = None
    start_line: int | None = None
    start_side: ReviewSide | None = None


class ReviewComment(pydantic.BaseModel):
    id: ResourceId
    html_url: str | None
    path: str
    body: str


class Review(pydantic.BaseModel):
    id: ResourceId
    html_url: str


class CheckRunOutput(pydantic.BaseModel):
    title: str
    summary: str
    text: str | None = None


class CheckRun(pydantic.BaseModel):
    id: ResourceId
    name: str
    status: BuildStatus
    conclusion: BuildConclusion | None
    html_url: str
