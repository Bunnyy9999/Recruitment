# DataRopes.ai Frontend Enhancement Prompt

You are working on the frontend for the DataRopes.ai recruitment platform. Build a modern, fast, and consistent web dashboard using the style of the provided DataRopes.ai logo and brand. The app should feel premium, clean, and operationally focused, while being optimized for speed and efficient API usage.

## Brand and UI direction
- Match the logo theme: dark navy / midnight blue base, white text, electric blue accents, and subtle premium gradients.
- Use this design consistently across the entire app.
- Replace the current “Command Center” page name with “Dashboard”.
- Add the DataRopes.ai logo prominently at the top of the main dashboard page.
- Adjust the logo size responsively so it looks sharp on desktop and smaller screens without breaking the layout.
- Keep the app visually consistent across all pages, including cards, filters, tables, buttons, and menus.

## Main dashboard page
This will be the main landing page of the web app.

Add a top header with:
- DataRopes.ai logo
- page title: Dashboard

Then show a grid of clickable summary cards with numeric values. Each card must be interactive and lead to a drill-down page or filter view.

Include these metric cards:
- Total Openings
- Total Opened Jobs
- Total Closed
- Total Applicants Applied in all jobs
- Total Applicants Passed Stage 1 (Sync)
- Total Applicants Currently in Interview Stages
- Total Applicants Whose First Technical Interview is Scheduled / Done
- Total Applicants Whose Second Technical Interview is Scheduled and Not Done
- Total Applicants Moved to CEO Review
- Total Successful Applicants
- Total Applicants Failed at CEO Review

The card hierarchy should be clear and intuitive:
- some cards are job-level metrics
- some are applicant-level metrics
- some are stage-based metrics
- when clicked, the app should drill into the relevant job or applicant list

## Drill-down behavior
When a user clicks a summary card, the app should open a dedicated view based on the card type.

### 1. Job overview drill-down
If the user clicks “Total Openings” or similar job-based cards:
- open a page with:
  - a dropdown of all jobs
  - each job entry showing:
    - job title
    - published date
    - total applicants
  - a search box
- when the user selects or searches for a specific job, open a detailed job page

### 2. Detailed job applicant page
This page should show a clean, structured table with all relevant fields for applicants in that job.

The table must be:
- well organized
- responsive
- readable on different screen widths
- better than the current table layout
- not cramped or visually broken
- optimized for horizontal scrolling when needed

Include fields such as:
- applicant name
- email
- phone
- linkedin
- application ID
- job title
- application stage
- sync result
- screening summary
- interview round status
- CEO review status
- final decision
- remarks
- created date

Important:
- if a value is too long for the column width, the cell should be clickable or expandable instead of breaking the layout
- allow hover states, truncation, and optional expansion for long text
- keep the table readable, professional, and compact

## Filter cards and stage filtering
On the detailed job page and dashboard drill-down pages, add clickable filter cards for stages such as:
- Passed at Sync
- Technical Interview 1 Scheduled
- Technical Interview 2 Scheduled
- CEO Review
- Successful
- Failed at Sync
- Failed at CEO Review

These filter cards should:
- update the visible applicant list instantly
- allow stage-based filtering with counts
- be visually prominent and clickable
- support both job-level and applicant-level drill-downs based on the selected metric

## Card-based navigation
The dashboard should use clickable metric cards that act like navigation entry points. Each card should represent a metric and a drill-down target.

For example:
- Total Openings card → job overview filter page
- Total Applicants Applied card → all applicants across all jobs
- Passed Stage 1 card → applicants filtered by sync pass
- Current Interview Stage card → applicant list filtered to interview pipeline
- CEO Review card → CEO review queue
- Successful Applicants card → final successful applicant list
- Failed at CEO Review card → rejected final decision list

Where possible, drill down from high-level totals to job-specific and applicant-specific views.

## Performance and API efficiency
This is a critical requirement. The app must remain very fast and responsive.

Implement the frontend with these performance principles:
- minimize unnecessary API calls
- use aggregated summary APIs for dashboard widgets
- fetch job and applicant data in batches instead of per row
- use cached data where possible
- avoid N+1 requests
- use lazy loading or pagination for large applicant tables
- debounce search input
- avoid reloading the whole page for filter changes
- only request the data needed for the current view
- use efficient state management and avoid repeated fetches on every render

The frontend should behave like a high-performance operations dashboard, not a slow prototype.

## Implementation expectations
- Keep all pages visually aligned with the DataRopes.ai theme
- Use a modern card layout and consistent design system
- Use strong contrast and clean spacing
- Hide clutter and focus on operational clarity
- Maintain consistent branding across dashboard, filter pages, and tables
- Ensure the experience feels premium and executive-ready

## Final objective
Create a polished dashboard-driven recruitment interface where users can:
- view system-wide metrics from the Dashboard
- click a metric to drill into relevant job or applicant data
- filter by stage and status
- inspect structured applicant records in a professional table
- navigate seamlessly from high-level insights to detailed records without confusion

Make the whole app feel like a premium DataRopes.ai operations dashboard with high-performance data access and a clear recruitment workflow.
