from playwright.sync_api import sync_playwright, expect


def test_steps_page() -> None:
    with sync_playwright() as playwright:
        my_browser = playwright.chromium.launch(headless=False)
        context = my_browser.new_context()
        # context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        # navigate to step list of the first campaign
        page.goto("http://0.0.0.0:8080/web_app/campaign/1/steps/")
        # check 1st step fullname is correct
        expect(page.get_by_text("HSC_DRP-Prod/test_panda/step1")).not_to_be_empty()
        # check number of groups is right
        expect(page.get_by_text("5 Group(s)")).not_to_be_empty()
        # check the campaign has 12 steps
        expect(page.locator(".step-card")).to_have_count(12)
        # check the first step card has a full width progress bar with green bg
        expect(page.locator(".step-card").first.filter(has=page.locator(".w-full"))).not_to_be_empty()
        expect(page.locator(".step-card").first.filter(has=page.locator(".bg-green-500"))).not_to_be_empty()
        # check campaign name is correct
        expect(page.get_by_text("test_panda", exact=True))
        # check clicking the first step name opens step details page
        page.get_by_role("link", name="step1").click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaign/1/1/")
        # check clicking campaign name breadcrumb
        # in step details opens step list page
        page.get_by_role("link", name="test_panda").click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaign/1/steps/")
        # check clicking production name opens campaigns page
        page.get_by_role("link", name="HSC_DRP-Prod").click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaigns/")
        # context.tracing.stop(path="trace2.zip")
        context.close()
        my_browser.close()
