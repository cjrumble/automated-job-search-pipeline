"""
run_pipeline.py  —  FIX 9: Complete rewrite

Original only called scrape_greenhouse("stripe") and returned a list.
It never called send_email, send_slack_alert, or any Sheets sync.
All scrapers and outputs are now wired together and driven by .env config.

Usage:
    python run_pipeline.py

Required .env vars:
    TARGET_ROLE, TARGET_LOCATION
    EMAIL_SENDER, EMAIL_RECIPIENT, EMAIL_PASSWORD
    SLACK_WEBHOOK
    GOOGLE_SHEET_NAME, GOOGLE_CREDENTIALS_PATH
    GREENHOUSE_COMPANIES  (comma-separated, e.g. "stripe,airbnb,shopify")
    LEVER_COMPANIES       (comma-separated, e.g. "netflix,datadog")
    LINKEDIN_ENABLED      (set to "true" to enable — requires chromedriver)
    OPENAI_API_KEY        (optional — enables AI job parsing)
"""

import os
from dotenv import load_dotenv

load_dotenv()                            # must come before any other local imports

from advanced_fit_score import advanced_fit_score
from dedupe_jobs        import dedupe_jobs
from estimate_salary    import estimate_salary
from priority_ranking   import rank_jobs, get_top_jobs
from scrape_greenhouse  import scrape_greenhouse
from scrape_lever       import scrape_lever
from scrape_remoteok    import scrape_remoteok
from send_email         import send_email
from send_slack_alert   import send_slack_alert
from sync_to_sheets     import sync_jobs_to_sheet

# AI parsing is optional — only runs when OPENAI_API_KEY is set
AI_PARSING_ENABLED = bool(os.getenv("OPENAI_API_KEY"))
if AI_PARSING_ENABLED:
    try:
        from job_smart_matching import parse_job
    except Exception:
        AI_PARSING_ENABLED = False


def _parse_companies(env_key):
    """Reads a comma-separated env var and returns a clean list of strings."""
    raw = os.getenv(env_key, "")
    return [c.strip() for c in raw.split(",") if c.strip()]


def run_pipeline():
    print("=" * 60)
    print("  Job Search Pipeline — Starting")
    print("=" * 60)

    all_jobs = []

    # ── Stage 1: Scrape all sources ───────────────────────────

    # Greenhouse  (public API, no auth needed, most reliable)
    greenhouse_companies = _parse_companies("GREENHOUSE_COMPANIES") or ["18F , 1Password, 23andMe, 3M Company, Abbott, ABM Industries, Accace, Accenture, Acivilate , Ad Hoc , AddStructure , Adecco, AdminaHealth, Adobe, Aecom, Aerostrat , Aerotek, Aetna, Affirma, AGCO, AIG, AirGarage , AirTreks , Algorand , Algorithmia , Allianz, Allied Universal, allyDVM , Alteryx, Altruist, Alvarez & Marsal, Amazon, Amazon Web Services (AWS), American Express, American Family Insurance, Anthology, Aon, APL Logistics, Apple, Applied Materials, Aramark, Aspire, Assurant, Astronomer , AT&T, ATPI, Autodesk, Avantor, AXA, Axios , Bain & Company, Baker McKenzie, Bank of America, Barclays, BBDO Worldwide, BCD Travel, Bear Group , Bechtel, Berkshire Hathaway Homestate Companies, Berkshire Hathaway Specialty Insurance, Better World Technology, BetterUp , Big Drop, Bill , Black & Veatch, BlackRock, Blameless , Bloc , BlueCat Networks , Bluespark , Boeing, Booking Holdings, Booz Allen Hamilton, Bop Design, Bosch, Boston Consulting Group, Box, BriteCore , Broadcom, BXP, Cable One, Cadence, Canon, Capco, Capgemini, Capital One, Carbon Black , Carlson Wagonlit Travel (CWT), Caterpillar, CBRE Group, CCI Tech, Cencora, Centene Corporation, Century 21 Real Estate, ChainLink Labs , Chargify , charity: water , Charles River Laboratories, Charles Schwab, Chevron, Cigna, Circonus , Cisco, Citadel, Citigroup, Clairvoyant, Clarivate, Clark Construction Group, Clarkson, Clay, Cloudera, Cloudflare, Cognizant, Coldwell Banker Realty, Colliers International, Compass Group, Compunnel Inc, Concentrix, Conley Realty Group, Continental, Continu , Core-Apps , Core-Mark, CoreOS , Corporate Travel Management, Corteva Agriscience, Costco, Coursera, Covington, Cox Communications, Cubix, Cummins, Cushman & Wakefield, CVS Health , Cyber Duo, Databricks, Datica , Davis Polk & Wardwell, DDB Worldwide, Dell Technologies, Deloitte, Delta Dental, Dentons, Dentsu, Designli, Dgraph , DHL, DICK'S Sporting Goods, Diffco, Direct Travel, Discord , DLA Piper, DollarDays, Dominion Energy, Dot Foods, Douglas Elliman, DPR Construction, DTE Energy, Duke Energy, DXC Technology, EatStreet , eBay, Elaine Bell Catering, Elevance Health, Elwood Staffing, Emcor, Enbridge, Enok , Entergy, Entrision , Epsilon, EssenceMediacom, Estately , EXL, ExxonMobil, EY, FedEx, Ferguson Enterprises, Fidelity Investments, Filament Group , FINEOS, FinThrive, FIS, Fisher Phillips, Flexera , Fluor Corporation, FMX , FOLX Health, Fortinet, FranklinCovey, Fuel Made , Gaggle , Gartner, GDIT, General Electric, General Motors, GEO Jobe , GHX, GigSalad , Gilbane Building Company, Gillead, Globant, Goldman Sachs, Google, Gorman Health Group , GotSoccer , Grainger, Grey Group, GroupM, Grubhub , GTS Distribution, GXO Logistics, Haley & Aldrich, Happy Cog , Havas Group, HCLTech, Headway , Healthfinch , Heartland Express, Hensel Phelps, Hogan Lovells, Honeywell, HP, HPE, HSBC, Hub Group, HubSpot, HughesNet, IBM, iFit , Impira , Indium Software, Infosys, Insight Global, INSPYR Solutions, Instructure, Intel, Intellias, Interpublic Group, Intevity , Intuit, IPS Group, Inc. , IQVIA, Ironclad, ISS Facility Services, J.B. Hunt, Jackson Lewis, Jackson River , Jacobs, JLL, John Deere, Johnson & Johnson, Jones Day, JPMorgan Chase, JupiterOne , KBS Services, Kearney, Keller Williams Realty, Kelly Services Global, Kenco, Khan Academy , Kiewit, Kirkland & Ellis, KPMG, Kyndryl, Labcorp, Latham & Watkins, Leidos, LEK Consulting, Lendlease, Leo Burnett, LeverX, LexisNexis, Liberty Mutual, Lincoln Loop , Lockheed Martin, Lumen Technologies, M16 Marketing, Marten Transport, Mastercard, Mathematica, Maximus, Mayvue , McKinsey, McLane Company, Mediacurrent , Mediavine , Medium , Merchants Insurance, Merck, MeridianLink , Meta, MetLife, Microsoft, Mindshare, Modern Health , Morgan Stanley, Mozilla , Nationwide , NetApp, New Context , Newmark Group, NEXT , Nextera Energy, NMS Consulting, Northern Trust, Northrop Grumman, npm , Nuna , Nvidia, Oak Street Health  , Oddball , Office Depot, Ogilvy, Oliver Wyman, Olo , OMD Worldwide, Omnicom Group, OmniTI , OneStream Software, Oracle, ORC Middleware Test Company , Orion Groups, Orrick, Our-Hometown Inc. , Oxagile, Palantir Technologies, Palantir.net , Palo Alto Networks, Parexel, Paylocity , PayScale , PCL Construction, Penske Logistics, Performance Food Group, Persistent, Pfizer, Philips 66, Pinnacle Financial Partners, PNC Financial Services , PowerSchool , Prelude , Procter & Gamble, Protiviti, Publicis Groupe, PwC, Qualcomm, Quanta Manufacturing Fremont, Randstad, Razorfish, Re:Build Manufacturing, Recurly , Redfin, Redox , Research Square , Rocketlane, Roland Berger, Saipem, Salesforce, SAP, ScienceSoft USA Corporation, Seagate Technology, ServiceNow, Seso, Shell, Sidley Austin, Siemens, Simon Property Group, Skanska USA, Skillsoft, SLB, SMX, Snowflake, Sodexo, Soostone , Sophos, Splunk, Spreedly , Stantec, Starlink, Suffolk Construction, Sullivan & Cromwell, Sure, Sysco, Sysdig️ , T-Mobile, TechMD, Teradata, Test Double , The Beck Group, The Walsh Group, Thermo Fisher Scientific, Third Iron , ThirdEye Data, Thomson Reuters, Thorn , TIBCO, Toast, Toptal, Tractionboard ️ , TrainingFolks, Trane Technologies, Travel Leaders Network, Treehouse , Tuft & Needle , Turner Construction, UCSF, UCSF Health, UL Solutions, Uline, Upworthy , US Bancorp, US Bank, US Foods, UST, Valero Energy Corp, Valimail , Vanguard, Veeva, Veolia, Verizon Communications, Vincent Brand Go, Vistaprint, VMware, WalletHub , Walmart, WebDevStudios , Wells Fargo, Wells Fargo , Whitecap SEO , Whiting Turner, Windstream Communications, WIPFLI, Wipro, Wix, WNS, Wombat Security, Workday, Workstate, WPP, Xcel Energy, XPO, Inc., Zip"]
    for company in greenhouse_companies:
        print(f"\n[Pipeline] Greenhouse → {company}")
        all_jobs.extend(scrape_greenhouse(company))

    # Lever  (public API, no auth needed)
    lever_companies = _parse_companies("LEVER_COMPANIES") or ["netflix, datadog, uber, lyft, pinterest, reddit, salesforce, square, twilio, 18F , 1Password, 23andMe, 3M Company, Abbott, ABM Industries, Accace, Accenture, Acivilate , Ad Hoc , AddStructure , Adecco, AdminaHealth, Adobe, Aecom, Aerostrat , Aerotek, Aetna, Affirma, AGCO, AIG, AirGarage , AirTreks , Algorand , Algorithmia , Allianz, Allied Universal, allyDVM , Alteryx, Altruist, Alvarez & Marsal, Amazon, Amazon Web Services (AWS), American Express, American Family Insurance, Anthology, Aon, APL Logistics, Apple, Applied Materials, Aramark, Aspire, Assurant, Astronomer , AT&T, ATPI, Autodesk, Avantor, AXA, Axios , Bain & Company, Baker McKenzie, Bank of America, Barclays, BBDO Worldwide, BCD Travel, Bear Group , Bechtel, Berkshire Hathaway Homestate Companies, Berkshire Hathaway Specialty Insurance, Better World Technology, BetterUp , Big Drop, Bill , Black & Veatch, BlackRock, Blameless , Bloc , BlueCat Networks , Bluespark , Boeing, Booking Holdings, Booz Allen Hamilton, Bop Design, Bosch, Boston Consulting Group, Box, BriteCore , Broadcom, BXP, Cable One, Cadence, Canon, Capco, Capgemini, Capital One, Carbon Black , Carlson Wagonlit Travel (CWT), Caterpillar, CBRE Group, CCI Tech, Cencora, Centene Corporation, Century 21 Real Estate, ChainLink Labs , Chargify , charity: water , Charles River Laboratories, Charles Schwab, Chevron, Cigna, Circonus , Cisco, Citadel, Citigroup, Clairvoyant, Clarivate, Clark Construction Group, Clarkson, Clay, Cloudera, Cloudflare, Cognizant, Coldwell Banker Realty, Colliers International, Compass Group, Compunnel Inc, Concentrix, Conley Realty Group, Continental, Continu , Core-Apps , Core-Mark, CoreOS , Corporate Travel Management, Corteva Agriscience, Costco, Coursera, Covington, Cox Communications, Cubix, Cummins, Cushman & Wakefield, CVS Health , Cyber Duo, Databricks, Datica , Davis Polk & Wardwell, DDB Worldwide, Dell Technologies, Deloitte, Delta Dental, Dentons, Dentsu, Designli, Dgraph , DHL, DICK'S Sporting Goods, Diffco, Direct Travel, Discord , DLA Piper, DollarDays, Dominion Energy, Dot Foods, Douglas Elliman, DPR Construction, DTE Energy, Duke Energy, DXC Technology, EatStreet , eBay, Elaine Bell Catering, Elevance Health, Elwood Staffing, Emcor, Enbridge, Enok , Entergy, Entrision , Epsilon, EssenceMediacom, Estately , EXL, ExxonMobil, EY, FedEx, Ferguson Enterprises, Fidelity Investments, Filament Group , FINEOS, FinThrive, FIS, Fisher Phillips, Flexera , Fluor Corporation, FMX , FOLX Health, Fortinet, FranklinCovey, Fuel Made , Gaggle , Gartner, GDIT, General Electric, General Motors, GEO Jobe , GHX, GigSalad , Gilbane Building Company, Gillead, Globant, Goldman Sachs, Google, Gorman Health Group , GotSoccer , Grainger, Grey Group, GroupM, Grubhub , GTS Distribution, GXO Logistics, Haley & Aldrich, Happy Cog , Havas Group, HCLTech, Headway , Healthfinch , Heartland Express, Hensel Phelps, Hogan Lovells, Honeywell, HP, HPE, HSBC, Hub Group, HubSpot, HughesNet, IBM, iFit , Impira , Indium Software, Infosys, Insight Global, INSPYR Solutions, Instructure, Intel, Intellias, Interpublic Group, Intevity , Intuit, IPS Group, Inc. , IQVIA, Ironclad, ISS Facility Services, J.B. Hunt, Jackson Lewis, Jackson River , Jacobs, JLL, John Deere, Johnson & Johnson, Jones Day, JPMorgan Chase, JupiterOne , KBS Services, Kearney, Keller Williams Realty, Kelly Services Global, Kenco, Khan Academy , Kiewit, Kirkland & Ellis, KPMG, Kyndryl, Labcorp, Latham & Watkins, Leidos, LEK Consulting, Lendlease, Leo Burnett, LeverX, LexisNexis, Liberty Mutual, Lincoln Loop , Lockheed Martin, Lumen Technologies, M16 Marketing, Marten Transport, Mastercard, Mathematica, Maximus, Mayvue , McKinsey, McLane Company, Mediacurrent , Mediavine , Medium , Merchants Insurance, Merck, MeridianLink , Meta, MetLife, Microsoft, Mindshare, Modern Health , Morgan Stanley, Mozilla , Nationwide , NetApp, New Context , Newmark Group, NEXT , Nextera Energy, NMS Consulting, Northern Trust, Northrop Grumman, npm , Nuna , Nvidia, Oak Street Health  , Oddball , Office Depot, Ogilvy, Oliver Wyman, Olo , OMD Worldwide, Omnicom Group, OmniTI , OneStream Software, Oracle, ORC Middleware Test Company , Orion Groups, Orrick, Our-Hometown Inc. , Oxagile, Palantir Technologies, Palantir.net , Palo Alto Networks, Parexel, Paylocity , PayScale , PCL Construction, Penske Logistics, Performance Food Group, Persistent, Pfizer, Philips 66, Pinnacle Financial Partners, PNC Financial Services , PowerSchool , Prelude , Procter & Gamble, Protiviti, Publicis Groupe, PwC, Qualcomm, Quanta Manufacturing Fremont, Randstad, Razorfish, Re:Build Manufacturing, Recurly , Redfin, Redox , Research Square , Rocketlane, Roland Berger, Saipem, Salesforce, SAP, ScienceSoft USA Corporation, Seagate Technology, ServiceNow, Seso, Shell, Sidley Austin, Siemens, Simon Property Group, Skanska USA, Skillsoft, SLB, SMX, Snowflake, Sodexo, Soostone , Sophos, Splunk, Spreedly , Stantec, Starlink, Suffolk Construction, Sullivan & Cromwell, Sure, Sysco, Sysdig️ , T-Mobile, TechMD, Teradata, Test Double , The Beck Group, The Walsh Group, Thermo Fisher Scientific, Third Iron , ThirdEye Data, Thomson Reuters, Thorn , TIBCO, Toast, Toptal, Tractionboard ️ , TrainingFolks, Trane Technologies, Travel Leaders Network, Treehouse , Tuft & Needle , Turner Construction, UCSF, UCSF Health, UL Solutions, Uline, Upworthy , US Bancorp, US Bank, US Foods, UST, Valero Energy Corp, Valimail , Vanguard, Veeva, Veolia, Verizon Communications, Vincent Brand Go, Vistaprint, VMware, WalletHub , Walmart, WebDevStudios , Wells Fargo, Wells Fargo , Whitecap SEO , Whiting Turner, Windstream Communications, WIPFLI, Wipro, Wix, WNS, Wombat Security, Workday, Workstate, WPP, Xcel Energy, XPO, Inc., Zip"]
    for company in lever_companies:
        print(f"[Pipeline] Lever → {company}")
        all_jobs.extend(scrape_lever(company))

    # RemoteOK  (public JSON API — replaced Indeed which blocks all scrapers)
    print("[Pipeline] RemoteOK → scraping...")
    all_jobs.extend(scrape_remoteok(
        role=os.getenv("TARGET_ROLE",     "QA Automation Engineer, QA, Qualiity Manager, Software Engineer in Test, SDET, Test Automation Engineer, Automation Developer, Software Quality Engineer, QA Analyst, QA Tester, Test Engineer, Quality Assurance Engineer, Project Manager, Technical Project Manager, TPM, IT Project Manager"),
        location=os.getenv("TARGET_LOCATION", "Remote, San Francisco, San Jose, Bay Area, CA, California, Mountain View, Palo Alto, Sunnyvale, Santa Clara, Fremont, Oakland, Berkeley, Richmond, Alameda, Pleasanton, Hayward, Menlo Park, Redwood City, Los Gatos, Campbell, Saratoga, Cupertino, Los Altos, Dublin, Newark, Union City, Milpitas, Morgan Hill, Gilroy, South San Francisco, San Bruno, Foster City, San Mateo, Belmont, San Carlos, Woodside, Portola Valley, Los Altos Hills, San Ramon, Danville, Alamo, Clayton, Concord, Martinez, Pinole, Hercules, El Cerrito, Kensington, Albany, Piedmont")
    ))

    # LinkedIn  (opt-in — requires chromedriver, set LINKEDIN_ENABLED=true)
    if os.getenv("LINKEDIN_ENABLED", "false").lower() == "true":
        try:
            from scrape_linkedin import scrape_linkedin
            print("[Pipeline] LinkedIn → scraping...")
            all_jobs.extend(scrape_linkedin(
                role=os.getenv("TARGET_ROLE"),
                location=os.getenv("TARGET_LOCATION")
            ))
        except Exception as e:
            print(f"[Pipeline] LinkedIn scraper skipped: {e}")

    print(f"\n[Pipeline] Raw jobs collected: {len(all_jobs)}")

    # ── Stage 2: Deduplicate ──────────────────────────────────
    all_jobs = dedupe_jobs(all_jobs)
    print(f"[Pipeline] After deduplication: {len(all_jobs)} jobs")

    if not all_jobs:
        print("[Pipeline] No jobs found. Check your scrapers and try again.")
        return []

    # ── Stage 3: Score each job ───────────────────────────────
    for job in all_jobs:
        job.setdefault("description", "")     # guard against missing key
        job["Fit Score"] = advanced_fit_score(job)
        job["Salary"]    = estimate_salary(job["title"])

        # Optional AI structured parsing
        if AI_PARSING_ENABLED and job["description"]:
            parsed = parse_job(job["description"])
            job["AI Skills"]    = ", ".join(parsed.get("skills", []))
            job["AI Seniority"] = parsed.get("seniority", "")

    # ── Stage 4: Rank by Fit Score ────────────────────────────
    ranked_jobs = rank_jobs(all_jobs)
    top_jobs    = get_top_jobs(ranked_jobs, n=10)

    print("\n[Pipeline] Top 10 by Fit Score:")
    for job in top_jobs:
        print(
            f"  #{job['Priority']:>2}  {job['Fit Score']}/10  "
            f"{job['title']} @ {job['company']}"
        )

    # ── Stage 5: Google Sheets sync ───────────────────────────
    print("\n[Pipeline] Syncing to Google Sheets...")
    sync_jobs_to_sheet(ranked_jobs)

    # ── Stage 6: Email digest ─────────────────────────────────
    print("[Pipeline] Sending email digest...")
    send_email(ranked_jobs)

    # ── Stage 7: Slack alert ──────────────────────────────────
    print("[Pipeline] Sending Slack alert...")
    send_slack_alert(top_jobs)

    print("\n" + "=" * 60)
    print(f"  Pipeline complete — {len(ranked_jobs)} jobs processed.")
    print("=" * 60)

    return ranked_jobs


if __name__ == "__main__":
    run_pipeline()
