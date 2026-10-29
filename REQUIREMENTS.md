# Example Site One — Requirements

Website for **Trattoria Bella Luna** (טרטוריה בלה לונה), a fictional family-run Italian restaurant in Tel Aviv.

**Language:** the site is entirely in **Hebrew**, laid out right to left (`lang="he" dir="rtl"`). All prices are in **Israeli new shekels (₪)**, including VAT.

## 1. Goals
- Show the restaurant's character: warm, rustic, family-run Italian.
- Let visitors browse the menu quickly on any device.
- Let visitors request a table reservation online.
- Make hours, address, and contact details easy to find.

## 2. Technology
- Plain **HTML5, CSS3, and vanilla JavaScript**: no frameworks, no build step.
- Files:
  - `index.html`: page structure and content
  - `styles.css`: all styling
  - `script.js`: all interactivity
- Opens directly in a browser (`index.html`) with no server needed.
- Only external dependency: Google Fonts (Frank Ruhl Libre and Heebo, both with Hebrew support).

## 3. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-1 | **Header / navigation**: fixed header with logo and links to every section. It gets a solid background after the user scrolls. |
| FR-2 | **Mobile menu**: below 768px, the nav collapses behind a hamburger toggle that opens and closes it. Choosing a link closes it. |
| FR-3 | **Hero**: full-height welcome section with the restaurant name, a tagline, and "לתפריט" (menu) and "הזמנת שולחן" (book a table) buttons. The background is a real evening photo of diners at an outdoor trattoria in Rome, under a dark overlay. |
| FR-4 | **About**: short story of the restaurant, plus three highlights (fresh pasta, wood-fired oven, family recipes). |
| FR-5 | **Menu**: dishes grouped into ראשונות, פסטות, פיצות, עיקריות, and קינוחים (antipasti, pasta, pizza, mains, desserts). Each dish has a photo of that dish, a Hebrew name, a description, and a price in ₪. |
| FR-6 | **Menu filter**: tab buttons ("All" plus each category) show only the chosen category. The active tab is highlighted. |
| FR-7 | **Gallery**: grid of real photos (food, a Roman street trattoria, Tuscan hills) with Hebrew captions. |
| FR-8 | **Reservation form**: fields for name, email, phone, date, time, guests (1–12), and optional notes. |
| FR-9 | **Form validation**: all required fields must be filled, the email must be valid, the phone needs at least 9 digits (Israeli format), the date can't be in the past or a Saturday (closed), and the time must be between 11:00 and 22:00 (last seating, one hour before the 23:00 close). Errors appear inline under each field, in Hebrew. |
| FR-10 | **Form confirmation**: on valid submission, show a success message that includes the guest's name, the party size, and the date (formatted with `he-IL`) and time, then reset the form. Nothing is sent to a server (front-end demo only). |
| FR-11 | **Contact / hours**: address, phone, email, and opening hours: Sunday–Friday 11:00–23:00, closed Saturday. |
| FR-12 | **Footer**: copyright with the current year filled in by JS, plus social links. |
| FR-13 | **Scroll reveal**: sections fade in as they scroll into view. |

## 4. Non-Functional Requirements
- **Responsive**: works from 320px phones up to large desktops, with no horizontal scrolling.
- **Section backgrounds**: real Italian photos set the mood: a Roman street behind the booking form, a red-and-white checked trattoria tablecloth (under a light cream overlay) behind the menu, and a Trastevere trattoria terrace behind the contact section (dark overlay).
- **RTL**: layout uses logical CSS properties (`inset-inline-start`, `padding-inline`, `border-inline-start`) so it mirrors correctly. Email and phone inputs stay left to right.
- **Accessible**: semantic landmarks, labels on every form field, `aria-expanded` on the menu toggle, visible focus styles, and colour contrast that meets WCAG AA.
- **Performance**: no heavy libraries. Photos are stored locally in `images/` (dishes) and `images/bg/` (backgrounds and gallery), resized to 960–1920px wide. Menu and gallery photos are lazy-loaded.
- **Licensing**: every photo is free-licensed from Wikimedia Commons and credited in `CREDITS.md`, which is linked from the footer.
- **Reduced motion**: animations are turned off when the user has `prefers-reduced-motion` set.
- **Browser support**: current versions of Chrome, Firefox, Safari, and Edge.

## 5. Design
- **Palette**: tomato red `#b5332e`, olive green `#5b6b3a`, cream `#faf5ec`, and charcoal `#2b2420`.
- **Typography**: Frank Ruhl Libre (headings) and Heebo (body text).
- **Tone**: warm, inviting, and traditional.

## 6. Out of Scope
- Real reservation backend or email sending
- Online ordering and payments
- CMS or admin panel
- Multiple languages (Hebrew only)
