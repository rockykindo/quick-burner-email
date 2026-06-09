import pytest
from playwright.sync_api import sync_playwright, expect

# Define the local hosting node port your Uvicorn server runs on
LOCAL_APP_URL = "http://127.0.0.1:8000"

def test_critical_ui_elements_render():
    """
    TEST 1: Verifies that all core interface controls, taglines,
    and placeholder elements render correctly in the viewport.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(LOCAL_APP_URL)
        
        # Verify brand identity and corrected grammatical tagline
        expect(page.locator("h1")).to_contain_text("Temp Email ID")
        expect(page.locator("p.text-gray-400").first).to_contain_text(
            "Generate an instant disposable email ID with no signups, no tracking, and pure speed."
        )
        
        # Verify critical control triggers are active on-screen
        expect(page.locator("#provider-select")).to_be_visible()
        expect(page.locator("#domain-select")).to_be_visible()
        expect(page.locator("#email-address")).to_be_visible()
        expect(page.locator("#generate-btn")).to_be_visible()
        expect(page.locator("#burn-btn")).to_be_visible()
        
        browser.close()

def test_engine_switching_isolation():
    """
    TEST 2: Verifies that switching engines completely resets the UI
    and does not leak email addresses between providers.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(LOCAL_APP_URL)
        
        # Select Guerrilla, click New, wait for an email to generate
        page.select_option("#provider-select", "guerrilla")
        page.click("#generate-btn")
        page.wait_for_timeout(1000) # Wait for network resolution
        
        g_email = page.input_value("#email-address")
        assert "Sync Required..." not in g_email
        
        # Switch to Mail.tm Premium Engine
        page.select_option("#provider-select", "mailtm")
        
        # CRITICAL TEST: The UI should instantly prompt a reset status 
        # instead of leaking the Guerrilla address into the Mail.tm view
        current_val = page.input_value("#email-address")
        assert current_val == "Sync Required..." or current_val == "Click New to Init..."
        
        browser.close()

def test_clipboard_copy_interaction():
    """
    TEST 3: Ensures copying to clipboard changes the button state to 'Copied!'
    """
    with sync_playwright() as p:
        # We need explicit clipboard permissions to test copy logic safely
        context = p.chromium.launch(headless=True).new_context(
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        page.goto(LOCAL_APP_URL)
        
        page.click("#generate-btn")
        page.wait_for_timeout(1000)
        
        # Trigger the clipboard copy mechanism
        page.click("#copy-btn")
        
        # The button layout should switch to success styles instantly
        expect(page.locator("#copy-btn")).to_have_text("Copied!")
        
        context.close()

def test_session_burn_panic_trigger():
    """
    TEST 4: Assures that clicking the Burn/Trash button completely 
    clears the workspace to factory settings.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(LOCAL_APP_URL)
        
        # Generate active tracking environment
        page.click("#generate-btn")
        page.wait_for_timeout(1000)
        
        # Hit the trash can reset button
        page.click("#burn-btn")
        
        # Interface must wipe out persistent values instantly
        expect(page.locator("#email-address")).to_have_value("Click New to Init...")
        expect(page.locator("#inbox-container")).to_contain_text("Session destroyed.")
        expect(page.locator("#status-badge")).to_have_text("Idle")
        
        browser.close()

def test_layout_shift_stability():
    """
    TEST 5: Confirms ad-placement containers retain fixed minimal heights
    to guarantee zero Cumulative Layout Shift (CLS) for AdSense compliance.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(LOCAL_APP_URL)
        
        # Target the explicit container IDs instead of inner text elements
        header_container = page.locator("#ad-zone-header")
        sidebar_container = page.locator("#ad-zone-sidebar")
        
        # Verify containers are visible and enforce strict sizing thresholds
        expect(header_container).to_be_visible()
        expect(sidebar_container).to_be_visible()
        
        assert header_container.bounding_box()["height"] >= 90
        assert sidebar_container.bounding_box()["height"] >= 200
        
        browser.close()
