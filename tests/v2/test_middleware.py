from httpx2 import AsyncClient


async def test_dynamic_root_path(aclient: AsyncClient) -> None:
    """Tests dynamic application of root path middleware"""
    root_path = "/cm-service"
    r = await aclient.get("/v2/campaigns/", follow_redirects=False)
    assert root_path not in r.headers["next"]

    # Test the application of dynamic root path when the request has trailing /
    r = await aclient.get("/v2/campaigns/", follow_redirects=False, headers={"x-forwarded-prefix": root_path})
    assert root_path in r.headers["next"]

    # Test the application of dynamic root path with a redirect, which will not
    # have a dynamic root path applied
    r = await aclient.get("/v2/campaigns", follow_redirects=False, headers={"x-forwarded-prefix": root_path})
    assert root_path not in r.headers["location"]
