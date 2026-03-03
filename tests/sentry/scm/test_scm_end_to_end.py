from collections.abc import Callable
from datetime import datetime
from typing import Literal

import pytest

from sentry.scm.client.scm_rpc_client import SourceCodeManagerRPCClient

# Currently, these tests can only run on my (jacquev6's) computer because they use:
# - my grok endpoint
# - personal repositories and apps I have set up on GitHub and GitLab
# - my Sentry dev server, configured to access these


@pytest.fixture(
    params=(
        params := [
            # https://github.com/jacquev6/test-Sentry-Integration-Dev-jacquev6
            ("GitHub external", ("github", "1159224812")),
            # ("GitHub internal", 1),
            # https://gitlab.com/jacquev6-sentry/test-sentry-integration-dev-jacquev6
            ("GitLab external", ("gitlab", "gitlab.com:79787061")),
            # ("GitLab internal", 2),
        ]
    ),
    ids=[p[0] for p in params],
)
def client(request: pytest.FixtureRequest) -> SourceCodeManagerRPCClient:
    return SourceCodeManagerRPCClient(
        base_url="http://reprovingly-smartish-jackqueline.ngrok-free.dev",
        shared_secret="yet-another-secret",
        organization_id=1,
        repository_id=request.param[1],
    )


type Service = Literal["github", "gitlab"]


@pytest.fixture
def service(request: pytest.FixtureRequest) -> Service:
    return request.node.callspec.params["client"][0].split()[0].lower()


type Switch[T] = Callable[[T, T], T]


@pytest.fixture
def switch(service: Service) -> Switch:
    def f[T](github: T, gitlab: T) -> T:
        match service:
            case "github":
                return github
            case "gitlab":
                return gitlab

    return f


def test_pull_requests(switch: Switch, client: SourceCodeManagerRPCClient) -> None:
    pull_requests = client.get_pull_requests()["data"]
    assert pull_requests == [
        {
            "id": switch("3329785233", "459277081"),
            "number": switch("2", "1"),
            "title": "Add blah",
            "body": None,
            "state": "open",
            "merged": False,
            "html_url": switch(
                "https://github.com/jacquev6/test-Sentry-Integration-Dev-jacquev6/pull/2",
                "https://gitlab.com/jacquev6-sentry/test-sentry-integration-dev-jacquev6/-/merge_requests/1",
            ),
            "head": {
                "sha": "6d8ca33dae268d3c5835e721e5702ef9dcb43c8c",
                "ref": "topics/blah",
            },
            "base": {
                "sha": switch("0941ee0a9eac9914cfddf5adec7a9558a2f1c447", None),
                "ref": "main",
            },
        }
    ]
    assert client.get_pull_request(switch("2", "1"))["data"] == pull_requests[0]
    new_pull_request = client.create_pull_request(
        title=f"PR from API {datetime.now()}",
        body="Another PR, made through the API.",
        head="topics/blih",
        base="main",
    )["data"]
    assert new_pull_request["body"] == "Another PR, made through the API."
    assert len(client.get_pull_requests()["data"]) == 2
    client.update_pull_request(new_pull_request["number"], state="closed")
    assert len(client.get_pull_requests()["data"]) == 1


def test_get_commits(switch: Switch, client: SourceCodeManagerRPCClient) -> None:
    assert client.get_commits(sha="1403774c82d64068af027d0b5d0cc4f52473b6f2")["data"] == [
        {
            "id": "1403774c82d64068af027d0b5d0cc4f52473b6f2",
            "message": "Initial commit",
            "author": {
                "name": "Vincent Jacques",
                "email": "vincent@vincent-jacques.net",
                "date": datetime.fromisoformat("2026-02-16T14:24:18+01:00"),
            },
            "files": switch([], None),
        }
    ]


def test_issue_comments(switch: Switch, client: SourceCodeManagerRPCClient) -> None:
    assert client.get_issue_comments("1")["data"] == [
        {
            "id": switch("3983150774", "3123861269"),
            "body": "A comment!",
            "author": {"id": switch("327146", "150871"), "username": "jacquev6"},
        }
    ]
    new_comment = client.create_issue_comment(
        issue_id="1", body="Another comment, made through the API."
    )["data"]
    assert new_comment["body"] == "Another comment, made through the API."
    assert len(client.get_issue_comments("1")["data"]) == 2
    client.delete_issue_comment(issue_id="1", comment_id=new_comment["id"])
    assert len(client.get_issue_comments("1")["data"]) == 1


def test_issue_comment_reactions(
    service: Service, switch: Switch, client: SourceCodeManagerRPCClient
) -> None:
    author = {"id": switch("327146", "150871"), "username": "jacquev6"}
    comment_id = switch("3983150774", "3123861269")
    reactions = client.get_issue_comment_reactions(issue_id="1", comment_id=comment_id)
    assert reactions["data"] == [
        {
            "id": switch("334443540", "43909506"),
            "content": "+1",
            "author": author,
        },
        {
            "id": switch("334443546", "43909515"),
            "content": "eyes",
            "author": author,
        },
        {
            "id": switch("334450300", "43911188"),
            "content": "-1",
            "author": author,
        },
        {
            "id": switch("334450310", "43911265"),
            "content": "laugh",
            "author": author,
        },
        {
            "id": switch("334450319", "43911283"),
            "content": "hooray",
            "author": author,
        },
        {
            "id": switch("334450331", "43911304"),
            "content": "confused",
            "author": author,
        },
        {
            "id": switch("334450342", "43911321"),
            "content": "heart",
            "author": author,
        },
    ]
    # One GitLab emoji is not mapped, so it's dropped silently
    assert len(reactions["raw"]) == switch(7, 8)
    new_reaction = client.create_issue_comment_reaction(
        issue_id="1", comment_id=comment_id, reaction="rocket"
    )["data"]
    assert new_reaction["content"] == "rocket"
    assert len(client.get_issue_comment_reactions(issue_id="1", comment_id=comment_id)["data"]) == 8
    client.delete_issue_comment_reaction(
        issue_id="1", comment_id=comment_id, reaction_id=new_reaction["id"]
    )
    assert len(client.get_issue_comment_reactions(issue_id="1", comment_id=comment_id)["data"]) == 7


def test_pull_request_comments(switch: Switch, client: SourceCodeManagerRPCClient) -> None:
    pull_request_id = switch("2", "1")
    assert client.get_pull_request_comments(pull_request_id)["data"] == [
        {
            "id": switch("3983417927", "3124015530"),
            "body": "A great comment!",
            "author": {"id": switch("327146", "150871"), "username": "jacquev6"},
        }
    ]
    new_comment = client.create_pull_request_comment(
        pull_request_id=pull_request_id, body="Another comment, made through the API."
    )["data"]
    assert new_comment["body"] == "Another comment, made through the API."
    assert len(client.get_pull_request_comments(pull_request_id)["data"]) == 2
    client.delete_pull_request_comment(
        pull_request_id=pull_request_id, comment_id=new_comment["id"]
    )
    assert len(client.get_pull_request_comments(pull_request_id)["data"]) == 1


def test_pull_request_comment_reactions(
    service: Service, switch: Switch, client: SourceCodeManagerRPCClient
) -> None:
    pull_request_id = switch("2", "1")
    comment_id = switch("3983417927", "3124015530")
    reactions = client.get_pull_request_comment_reactions(
        pull_request_id=pull_request_id, comment_id=comment_id
    )
    assert reactions["data"] == [
        {
            "id": switch("334495774", "43921665"),
            "content": "+1",
            "author": {"id": switch("327146", "150871"), "username": "jacquev6"},
        }
    ]
    # One GitLab emoji is not mapped, so it's dropped silently
    assert len(reactions["raw"]) == switch(1, 2)
    new_reaction = client.create_pull_request_comment_reaction(
        pull_request_id=pull_request_id, comment_id=comment_id, reaction="rocket"
    )["data"]
    assert new_reaction["content"] == "rocket"
    assert (
        len(
            client.get_pull_request_comment_reactions(
                pull_request_id=pull_request_id, comment_id=comment_id
            )["data"]
        )
        == 2
    )
    client.delete_pull_request_comment_reaction(
        pull_request_id=pull_request_id, comment_id=comment_id, reaction_id=new_reaction["id"]
    )
    assert (
        len(
            client.get_pull_request_comment_reactions(
                pull_request_id=pull_request_id, comment_id=comment_id
            )["data"]
        )
        == 1
    )


def test_issue_reactions(
    service: Service, switch: Switch, client: SourceCodeManagerRPCClient
) -> None:
    issue_id = "1"
    reactions = client.get_issue_reactions(issue_id)
    assert reactions["data"] == [
        {
            "id": switch("277533978", "43923647"),
            "content": "+1",
            "author": {"id": switch("327146", "150871"), "username": "jacquev6"},
        },
        {
            "id": switch("277533995", "43923674"),
            "content": "hooray",
            "author": {"id": switch("327146", "150871"), "username": "jacquev6"},
        },
    ]
    # One GitLab emoji is not mapped, so it's dropped silently
    assert len(reactions["raw"]) == switch(2, 3)
    new_reaction = client.create_issue_reaction(issue_id=issue_id, reaction="rocket")["data"]
    assert new_reaction["content"] == "rocket"
    assert len(client.get_issue_reactions(issue_id)["data"]) == 3
    client.delete_issue_reaction(issue_id=issue_id, reaction_id=new_reaction["id"])
    assert len(client.get_issue_reactions(issue_id)["data"]) == 2


def test_pull_request_reactions(
    service: Service, switch: Switch, client: SourceCodeManagerRPCClient
) -> None:
    pull_request_id = switch("2", "1")
    reactions = client.get_pull_request_reactions(pull_request_id)
    assert reactions["data"] == [
        {
            "id": switch("277538935", "43924243"),
            "content": "-1",
            "author": {"id": switch("327146", "150871"), "username": "jacquev6"},
        }
    ]
    # One GitLab emoji is not mapped, so it's dropped silently
    assert len(reactions["raw"]) == switch(1, 2)
    new_reaction = client.create_pull_request_reaction(
        pull_request_id=pull_request_id, reaction="rocket"
    )["data"]
    assert new_reaction["content"] == "rocket"
    assert len(client.get_pull_request_reactions(pull_request_id)["data"]) == 2
    client.delete_pull_request_reaction(
        pull_request_id=pull_request_id, reaction_id=new_reaction["id"]
    )
    assert len(client.get_pull_request_reactions(pull_request_id)["data"]) == 1
