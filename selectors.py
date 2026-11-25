"""
selectors.py – Central registry of CSS/text selectors for Naukri.com
=======================================================================
⚠  Naukri's frontend changes frequently.  When a selector breaks:
   1. Open DevTools on the failing page.
   2. Find the new element and copy its selector.
   3. Update the constant here and re-run --dry-run to verify.

Selector strategies used (in order of preference):
  • Role/text locators  → most resilient to class-name churn
  • data-* attributes   → more stable than generated class names
  • CSS class names      → last resort; flag them with  # FRAGILE
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Login page  (naukri.com/nlogin/login)
# ---------------------------------------------------------------------------
LOGIN_EMAIL_INPUT     = "input[placeholder*='Email']"       # FRAGILE – fallback
LOGIN_EMAIL_LABEL     = "Email ID / Username"               # for get_by_label
LOGIN_PASSWORD_INPUT  = "input[type='password']"
LOGIN_SUBMIT_BTN      = "Login"                             # used with exact=True to avoid "Use OTP to Login"
LOGIN_SUCCESS_COOKIE  = "nauk_at"                          # cookie present on success

# Captcha / verification detection
CAPTCHA_INDICATORS = [
    "captcha",
    "verify you are not a robot",
    "verify that you are human",
    "complete the security check",
]
OTP_INDICATORS = [
    "enter otp",
    "otp sent",
    "verify your mobile",
    "verify your email",
]

# ---------------------------------------------------------------------------
# Profile / Dashboard page
# ---------------------------------------------------------------------------
PROFILE_NAV_LINK          = "naukri.com/mnjuser/profile"        # URL substring
PROFILE_HEADLINE_CONTAINER = "#lazyResumeHead"                  # verified on live site
RESUME_HEADLINE_EDIT_BTN  = "#lazyResumeHead .edit.icon, #lazyResumeHead [aria-label*='Edit']" # verified
RESUME_HEADLINE_FIELD     = "#resumeHeadlineTxt, textarea.fue__text-area, textarea[placeholder*='headline']" # verified
RESUME_HEADLINE_CANCEL_BTN = ".action .cancel-btn, button:has-text('Cancel'), a:has-text('Cancel')"
RESUME_HEADLINE_SAVE_BTN  = "button.btn-dark-ot:has-text('Save'), button[type='submit']:has-text('Save')" # verified

# Resume upload
RESUME_UPLOAD_BTN         = "text=Update Resume"                 # FRAGILE
RESUME_FILE_INPUT         = "input[type='file']"

# ---------------------------------------------------------------------------
# Profile page – skill / experience scraping  (used by profile_reader.py)
# ---------------------------------------------------------------------------
# Key Skills chips (the tag-like pills shown under Skills section)
PROFILE_SKILL_CHIP        = "#lazyKeySkills span.chip"          # verified on live site
PROFILE_SKILL_CHIP_ALT    = "span.chipText"                     # FRAGILE – fallback

# Current designation / job title shown on profile summary card
PROFILE_DESIGNATION       = "div.designation"                   # FRAGILE
PROFILE_DESIGNATION_ALT   = "[class*='desig']"                  # FRAGILE – alternate

# Experience summary text, e.g. "3 Years 2 Months"
PROFILE_EXPERIENCE        = "div.experience"                    # FRAGILE
PROFILE_EXPERIENCE_ALT    = "[class*='expwrp'] span"            # FRAGILE

# Resume headline (display text + edit textarea)
PROFILE_HEADLINE          = "#lazyResumeHead .widgetCont"       # verified on live site
PROFILE_HEADLINE_INPUT    = "textarea[placeholder*='headline']" # FRAGILE – edit modal

# ---------------------------------------------------------------------------
# Job search results page
# ---------------------------------------------------------------------------
SEARCH_BOX_WHAT           = "input[placeholder*='skills, designations']"  # FRAGILE
SEARCH_BOX_WHERE          = "input[placeholder*='location']"              # FRAGILE
SEARCH_SUBMIT_BTN         = "Search"                                       # get_by_role

# Individual job card in the listing
JOB_CARD_CONTAINER        = "div[data-job-id]"                 # verified on live site (20/page)
JOB_CARD_TITLE            = "a.title"                          # verified – within card
JOB_CARD_COMPANY          = ".comp-name"                       # verified – within card
JOB_CARD_LOCATION         = ".loc-wrap, .locWdth"              # verified – within card
JOB_CARD_EXPERIENCE       = ".exp, .expwdth"                   # FRAGILE – within card
JOB_CARD_SALARY           = ".sal, .salary"                    # FRAGILE – within card
JOB_CARD_POSTED           = ".job-post-day, .type"             # FRAGILE – within card
JOB_CARD_LINK             = "a.title"                          # verified – within card

# Pagination
NEXT_PAGE_BTN             = "[class*='pagination'] a:has-text('Next')"  # verified container

# ---------------------------------------------------------------------------
# Job detail page
# ---------------------------------------------------------------------------
APPLY_BTN_PRIMARY         = "button#apply-button"              # FRAGILE
APPLY_BTN_TEXT_FALLBACK   = "Apply"                            # get_by_role text
EXTERNAL_APPLY_INDICATOR  = [
    "Apply on company site",
    "Apply on employer site",
    "Apply via company",
]
JOB_DETAIL_TITLE          = "h1.jd-header-title"              # FRAGILE
JOB_DETAIL_COMPANY        = "a.jd-header-comp-name"           # FRAGILE
JOB_DETAIL_DESCRIPTION    = ".job-desc"                       # FRAGILE

# Post-apply confirmation signals
APPLY_SUCCESS_SIGNALS = [
    "Applied successfully",
    "Application submitted",
    "You have already applied",
    "applied for this job",
]

# Questionnaire / chatbot overlay
QUESTIONNAIRE_OVERLAY     = ".apply-questionnaire"            # FRAGILE
QUESTIONNAIRE_CLOSE_BTN   = "button[title*='close']"          # FRAGILE
CHATBOT_CONTAINER         = ".chatbot-container"              # FRAGILE

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
COOKIE_ACCEPT_BTN         = "text=Accept"                      # cookie banner
PAGE_LOADER               = ".loading-screen"                  # wait for it to vanish
