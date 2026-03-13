from __future__ import annotations


def landing_page_html() -> str:
    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Arch City Tutors Preview</title>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
  <link href=\"https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Sora:wght@400;500;600;700;800&display=swap\" rel=\"stylesheet\" />
  <style>
    :root {
      --bg: #07080d;
      --panel: rgba(10, 8, 12, 0.93);
      --line: rgba(255, 255, 255, 0.08);
      --text: #f5f0ee;
      --muted: rgba(245, 240, 238, 0.72);
      --accent: #e10f17;
      --accent-soft: rgba(225, 15, 23, 0.16);
      --glow: rgba(202, 32, 39, 0.42);
      --green: #58d36f;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: 'Outfit', sans-serif;
      background:
        radial-gradient(circle at 12% 14%, rgba(179, 25, 29, 0.38), transparent 24%),
        radial-gradient(circle at 60% 18%, rgba(225, 15, 23, 0.32), transparent 20%),
        radial-gradient(circle at 92% 20%, rgba(121, 15, 19, 0.28), transparent 24%),
        linear-gradient(180deg, #18070a 0%, #05060a 44%, #030407 100%);
      color: var(--text);
      padding: 16px;
    }

    .frame {
      position: relative;
      overflow: hidden;
      min-height: calc(100vh - 32px);
      border-radius: 28px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      background:
        radial-gradient(circle at center, rgba(191, 22, 28, 0.22), transparent 34%),
        radial-gradient(circle at center, rgba(133, 13, 17, 0.16), transparent 52%),
        linear-gradient(180deg, rgba(23, 5, 7, 0.9), rgba(2, 4, 8, 0.98));
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 24px 90px rgba(0,0,0,0.38);
    }

    .frame::before,
    .frame::after {
      content: '';
      position: absolute;
      inset: auto;
      width: 720px;
      height: 720px;
      border-radius: 50%;
      pointer-events: none;
      opacity: 0.45;
      filter: blur(16px);
    }

    .frame::before {
      top: -360px;
      left: -180px;
      background: radial-gradient(circle, rgba(161, 21, 27, 0.56), transparent 60%);
    }

    .frame::after {
      top: -340px;
      right: -200px;
      background: radial-gradient(circle, rgba(120, 7, 13, 0.45), transparent 62%);
    }

    .shell {
      max-width: 1320px;
      margin: 0 auto;
      padding: 28px 28px 56px;
      position: relative;
      z-index: 1;
    }

    .nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }

    .brand {
      display: inline-flex;
      align-items: center;
      gap: 14px;
      text-decoration: none;
      color: var(--text);
    }

    .brand-mark {
      width: 48px;
      height: 48px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
      border: 1px solid rgba(255,255,255,0.1);
      box-shadow: 0 10px 30px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.08);
      position: relative;
      overflow: hidden;
    }

    .brand-mark::before {
      content: '';
      position: absolute;
      inset: 10px 13px 14px;
      border-radius: 8px 8px 4px 4px;
      background: linear-gradient(180deg, #ff2730, #94090f);
      clip-path: polygon(50% 0%, 100% 40%, 100% 100%, 0 100%, 0 40%);
      box-shadow: 0 0 22px rgba(225, 15, 23, 0.35);
    }

    .brand-copy {
      display: grid;
      line-height: 1;
    }

    .brand-copy strong {
      font-family: 'Sora', sans-serif;
      font-size: 1.45rem;
      letter-spacing: 0.08em;
      color: #ff2c34;
    }

    .brand-copy span {
      font-size: 0.78rem;
      letter-spacing: 0.42em;
      color: rgba(255,255,255,0.88);
      margin-left: 0.1em;
    }

    .menu {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 32px;
      flex: 1;
      min-width: 0;
    }

    .menu a,
    .auth a {
      color: rgba(255,255,255,0.92);
      text-decoration: none;
      font-weight: 600;
      font-size: 1.06rem;
    }

    .menu a:hover,
    .auth a:hover { color: #ffffff; }

    .auth {
      display: flex;
      align-items: center;
      gap: 20px;
    }

    .cta {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 52px;
      padding: 0 24px;
      border-radius: 999px;
      background: linear-gradient(135deg, #ff1c27, #c30712);
      color: white;
      box-shadow: 0 16px 40px rgba(199, 11, 21, 0.3);
    }

    .hero {
      padding: 72px 0 24px;
      display: grid;
      place-items: center;
      text-align: center;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 18px;
      border-radius: 999px;
      color: rgba(255,255,255,0.92);
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.03);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
      margin-bottom: 28px;
      font-weight: 600;
    }

    .badge::before {
      content: '';
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 12px rgba(88, 211, 111, 0.75);
    }

    h1 {
      margin: 0;
      max-width: 920px;
      font-family: 'Sora', sans-serif;
      font-size: clamp(3.8rem, 8vw, 6.9rem);
      line-height: 0.92;
      letter-spacing: -0.06em;
      text-wrap: balance;
    }

    .accent {
      color: #f7e9e6;
      text-shadow: 0 0 28px rgba(255,255,255,0.08);
    }

    .hero p {
      max-width: 700px;
      margin: 22px auto 0;
      color: var(--muted);
      font-size: 1.16rem;
      line-height: 1.7;
    }

    .hero-actions {
      display: flex;
      align-items: center;
      gap: 16px;
      margin-top: 34px;
      flex-wrap: wrap;
      justify-content: center;
    }

    .primary,
    .secondary {
      min-height: 54px;
      padding: 0 24px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      font-weight: 700;
      letter-spacing: 0.01em;
    }

    .primary {
      background: linear-gradient(135deg, #ff1b27, #c50712);
      color: #fff;
      box-shadow: 0 16px 36px rgba(229, 17, 27, 0.28);
    }

    .secondary {
      border: 1px solid rgba(255,255,255,0.14);
      color: rgba(255,255,255,0.9);
      background: rgba(255,255,255,0.03);
    }

    .showcase {
      margin: 58px auto 0;
      width: min(960px, 100%);
      background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 28px;
      padding: 22px;
      box-shadow: 0 28px 60px rgba(0,0,0,0.36);
    }

    .window-bar {
      display: flex;
      align-items: center;
      gap: 9px;
      margin-bottom: 18px;
    }

    .window-bar span {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: rgba(255,255,255,0.18);
    }

    .window-bar span:first-child { background: #ff5f57; }
    .window-bar span:nth-child(2) { background: #febc2e; }
    .window-bar span:nth-child(3) { background: #28c840; }

    .card-grid {
      display: grid;
      grid-template-columns: 1.5fr 1fr;
      gap: 18px;
    }

    .panel {
      padding: 24px;
      border-radius: 24px;
      background: rgba(5, 7, 12, 0.86);
      border: 1px solid rgba(255,255,255,0.06);
      min-height: 260px;
    }

    .panel h2,
    .panel h3 {
      margin: 0;
      font-family: 'Sora', sans-serif;
    }

    .stat {
      margin-top: 22px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }

    .stat div {
      padding: 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
      border: 1px solid rgba(255,255,255,0.06);
    }

    .stat strong {
      display: block;
      font-size: 1.45rem;
      margin-bottom: 8px;
    }

    .pill-list {
      margin-top: 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .pill-list span {
      padding: 10px 14px;
      border-radius: 999px;
      background: var(--accent-soft);
      border: 1px solid rgba(225, 15, 23, 0.26);
      color: #ffd9db;
      font-weight: 600;
      font-size: 0.92rem;
    }

    @media (max-width: 1080px) {
      .nav {
        flex-wrap: wrap;
        justify-content: center;
      }

      .menu {
        order: 3;
        width: 100%;
        flex-wrap: wrap;
        gap: 18px 24px;
      }
    }

    @media (max-width: 760px) {
      body { padding: 10px; }
      .frame { min-height: calc(100vh - 20px); border-radius: 22px; }
      .shell { padding: 20px 18px 38px; }
      .auth { width: 100%; justify-content: center; }
      .card-grid { grid-template-columns: 1fr; }
      .stat { grid-template-columns: 1fr; }
      h1 { font-size: clamp(3rem, 16vw, 4.5rem); }
      .hero { padding-top: 56px; }
    }
  </style>
</head>
<body>
  <main class=\"frame\">
    <div class=\"shell\">
      <nav class=\"nav\">
        <a class=\"brand\" href=\"#\">
          <span class=\"brand-mark\" aria-hidden=\"true\"></span>
          <span class=\"brand-copy\">
            <strong>ARCH CITY</strong>
            <span>TUTORS</span>
          </span>
        </a>

        <div class=\"menu\">
          <a href=\"#pricing\">Pricing</a>
          <a href=\"#about\">About Us</a>
          <a href=\"#students\">Students</a>
          <a href=\"#tutors\">Tutors</a>
          <a href=\"#contact\">Contact Us</a>
          <a href=\"#faq\">FAQs</a>
        </div>

        <div class=\"auth\">
          <a href=\"#login\">Login</a>
          <a class=\"cta\" href=\"#signup\">Create Account</a>
        </div>
      </nav>

      <section class=\"hero\">
        <span class=\"badge\">BETA 1.0 AVAILABLE NOW</span>
        <h1>
          <span class=\"accent\">Tutoring Made</span><br />
          Simple, Structured, and Personal.
        </h1>
        <p>
          A premium tutoring platform for students and families who want trusted mentors,
          fast scheduling, and a dashboard that feels calm instead of chaotic.
        </p>
        <div class=\"hero-actions\">
          <a class=\"primary\" href=\"#start\">Start Learning</a>
          <a class=\"secondary\" href=\"#tour\">Watch Platform Tour</a>
        </div>

        <div class=\"showcase\">
          <div class=\"window-bar\"><span></span><span></span><span></span></div>
          <div class=\"card-grid\">
            <div class=\"panel\">
              <h2>High-trust tutoring, built for outcomes.</h2>
              <p style=\"color: var(--muted); line-height: 1.7; margin-top: 16px;\">
                Match students with vetted tutors, track progress session by session, and keep parents in the loop without adding admin overhead.
              </p>
              <div class=\"stat\">
                <div><strong>1:1</strong><span style=\"color: var(--muted);\">Private sessions</span></div>
                <div><strong>24h</strong><span style=\"color: var(--muted);\">Fast matching</span></div>
                <div><strong>98%</strong><span style=\"color: var(--muted);\">Family retention</span></div>
              </div>
            </div>
            <div class=\"panel\">
              <h3 style=\"font-size: 1.35rem;\">Platform highlights</h3>
              <div class=\"pill-list\">
                <span>Verified tutors</span>
                <span>Progress reports</span>
                <span>Flexible billing</span>
                <span>Parent messaging</span>
                <span>Session playback</span>
                <span>Live availability</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </main>
</body>
</html>
"""
