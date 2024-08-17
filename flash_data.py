league_urls = [
    "https://www.flashscore.co.uk/football/england/premier-league/",
    "https://www.flashscore.co.uk/football/england/championship/",
    "https://www.flashscore.co.uk/football/england/league-one/",
    "https://www.flashscore.co.uk/football/england/league-two/",
    "https://www.flashscore.co.uk/football/scotland/premiership/",
    "https://www.flashscore.co.uk/football/france/ligue-1/",
    "https://www.flashscore.co.uk/football/germany/bundesliga/",
    "https://www.flashscore.co.uk/football/italy/serie-a/",
    "https://www.flashscore.co.uk/football/spain/laliga/",
    "https://www.flashscore.co.uk/football/netherlands/eredivisie/",
    "https://www.flashscore.co.uk/football/portugal/liga-portugal/",
    "https://www.flashscore.co.uk/football/brazil/serie-a/",
    "https://www.flashscore.co.uk/football/norway/eliteserien/",
    "https://www.flashscore.co.uk/football/sweden/allsvenskan/",
    "https://www.flashscore.co.uk/football/usa/mls/",
]

league_urls = sorted(list(set(league_urls)))
league_urls.extend(["Sync whole history", "Update latest season"])

import sys
from datetime import date
from time import perf_counter

import pandas as pd
from time import sleep
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)


#################################### FETCH DATA #########################################
def create_driver():
    return webdriver.Chrome(
        options=options, service=Service(ChromeDriverManager().install())
    )


def create_soup(html):
    return BeautifulSoup(html, "html.parser")


def get_soup(url: str):
    try:
        driver = create_driver()
        driver.get(url)
        soup = create_soup(driver.page_source)
        driver.quit()
    except Exception as e:
        print(f"Error parsing {url}")
        return None
    finally:
        driver.quit()
        return soup


##


def get_matches_from_tables(soup_list):
    tables = []
    match_urls = []
    for soup in soup_list:
        soup = create_soup(soup)
        for x in soup.find_all(class_="leagues--static event--leagues results"):
            tables.append(x)

    for table in tables:
        for idx, row in enumerate(table.find_all("div"), 1):
            match_id = row.get("id")
            if not match_id:
                continue
            match_id = match_id.split("_")[-1]
            match_url = f"https://www.flashscore.co.uk/match/{match_id}/#/match-summary/match-summary"
            match_urls.append(match_url)
    print(f" [*] TOTAL matches found --> {len(match_urls)}")
    return match_urls


def get_matches_per_season(urls, index=1):
    soup_list = []
    all_match_urls = []  # This will accumulate all match URLs
    print(f"index: {index}")
    # for url in urls:  # Iterate over all URLs
    for url in urls:
        try:
            print(f" [+] Fetching {url}")
            driver = create_driver()
            driver.get(url)

            # Attempt to find the "Show more matches" button and click it until it is no longer found
            element = driver.find_elements(By.LINK_TEXT, "Show more matches")[index]
            while element:
                driver.execute_script("arguments[0].click();", element)
                print(f" [!] Pausing to load the page contents")
                sleep(2)
                try:
                    element = driver.find_elements(By.LINK_TEXT, "Show more matches")[index]
                except:
                    break  # Exit loop if the button is no longer found

        except Exception as e:
            print(f' [-] Warning: Could not process URL: {url} - {e}')
            pass

        finally:
            html = driver.page_source
            if html:
                match_urls = get_matches_from_tables([html])  # Process the current HTML
                all_match_urls.extend(match_urls)  # Accumulate the results            

    driver.quit()
    return all_match_urls

def save_html_to_file(html_content, filename):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(html_content)
        print(f" [+] Saved HTML to {filename}")


def match_summary(urls: list):
    data = []
    try:
        driver = create_driver()
        for nb, url in enumerate(urls, 1):
            t1_start = perf_counter()
            driver.get(url)
            sleep(1)
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "smv__verticalSections.section")
                )
            )
            soup = create_soup(driver.page_source)
            js = create_js(soup, url)
            # print('-' * 100)
            tmp_js1 = craft_js()
            tmp_js = {**tmp_js1, **js}
            data.append(tmp_js)
            t1_stop = perf_counter()
            T = round(t1_stop - t1_start, 2)
            print(f"{len(urls)-nb+1:>3}/{len(urls)} --> {url} {T:>4}", end="\r")
    except Exception as e:
        print(f"Error parsing {url}", e)
        # return None
    finally:
        driver.quit()
        return data


#################################### XTRACT DATA #########################################
def find_incident(svg_class, svg_data_testid, data, team, url):
    if "wcl-icon-soccer" in svg_data_testid:
        res = team + "_G"
    if "yellowCard-ico" in svg_class:
        res = team + "_Y"
    if "redCard-ico" in svg_class:
        res = team + "_R"
    if ["card-ico"] == svg_class:
        res = team + "_YR"
    try:
        return res
    except:
        print(f"ERROR - {svg_class} - {svg_data_testid} - {data} - {team}")
        print(f"ERROR finding incident in {url}")
        return None


def incident_time(team, inp, url):
    data = []
    for x in inp:
        js = {}
        try:
            time = (
                x.find(class_="smv__incident")
                .find(class_="smv__timeBox")
                .text.replace("'", "")
                .split("+")[0]
            )
            svg_tag = x.find("svg")
            svg_class = svg_tag.get("class", "")
            svg_data_testid = svg_tag.get("data-testid", "")
        except:
            continue
        if any(
            keyword in svg_class
            for keyword in ["substitution", "var", "warning", "arrow"]
        ):
            continue
        incident = find_incident(svg_class, svg_data_testid, data, team, url)
        if not incident:
            continue
        js[incident] = time
        data.append(js)
    return data


def add_counter(inp, T):
    k = lambda x: list(x.keys())[0]
    v = lambda x: list(x.values())[0]
    js = {}
    i = 1
    for x in inp:
        if k(x) != T:
            continue
        js[k(x) + str(i)] = v(x)
        i += 1
    return js


#################################### PREPARE DATA #########################################
def craft_js():
    return {
        "date": "",
        "tournament": "",
        "home_team": "",
        "away_team": "",
        "home_goals": "",
        "away_goals": "",
        "H_G1": "",
        "H_G2": "",
        "H_G3": "",
        "H_G4": "",
        "H_G5": "",
        "H_G6": "",
        "H_G7": "",
        "H_G8": "",
        "H_G9": "",
        "H_G10": "",
        "H_Y1": "",
        "H_Y2": "",
        "H_Y3": "",
        "H_Y4": "",
        "H_Y5": "",
        "H_Y6": "",
        "H_Y7": "",
        "H_Y8": "",
        "H_Y9": "",
        "H_Y10": "",
        "H_R1": "",
        "H_R2": "",
        "H_R3": "",
        "H_R4": "",
        "H_R5": "",
        "H_YR1": "",
        "H_YR2": "",
        "H_YR3": "",
        "H_YR4": "",
        "H_YR5": "",
        "A_G1": "",
        "A_G2": "",
        "A_G3": "",
        "A_G4": "",
        "A_G5": "",
        "A_G6": "",
        "A_G7": "",
        "A_G8": "",
        "A_G9": "",
        "A_G10": "",
        "A_Y1": "",
        "A_Y2": "",
        "A_Y3": "",
        "A_Y4": "",
        "A_Y5": "",
        "A_Y6": "",
        "A_Y7": "",
        "A_Y8": "",
        "A_Y9": "",
        "A_Y10": "",
        "A_R1": "",
        "A_R2": "",
        "A_R3": "",
        "A_R4": "",
        "A_R5": "",
        "A_YR1": "",
        "A_YR2": "",
        "A_YR3": "",
        "A_YR4": "",
        "A_YR5": "",
        "Referee": "",
        "Venue": "",
        "Attendance": "",
    }


def create_js(soup, url):
    js = {}
    js["_id"] = url.split("/")[-4]
    js["date"] = soup.find(class_="duelParticipant__startTime").find("div").text
    js["tournament"] = "_".join(
        soup.find(class_="tournamentHeader__country")
        .find("a")
        .get("href")
        .split("/")[2:-1]
    )
    js["home_team"] = soup.find(class_="duelParticipant__home").text
    js["away_team"] = soup.find(class_="duelParticipant__away").text
    score = [y.text for y in soup.find(class_="detailScore__wrapper").find_all("span")]
    js["home_goals"] = score[0]
    js["away_goals"] = score[-1]

    section = soup.find(class_="smv__verticalSections section")
    home = section.find_all(class_="smv__homeParticipant")
    away = section.find_all(class_="smv__awayParticipant")
    home_data = incident_time("H", home, url)
    away_data = incident_time("A", away, url)
    h_inc = ["H_G", "H_Y", "H_R", "H_YR"]
    a_inc = ["A_G", "A_Y", "A_R", "A_YR"]

    for T1, T2 in zip(h_inc, a_inc):
        js.update(add_counter(home_data, T1))
        js.update(add_counter(away_data, T2))

    try:
        name_detils = soup.find(class_="wclDetailSection").find_all("strong")
        j = 0
        end_details = soup.find(class_="wclDetailSection").find_all("span")
        for i, x in enumerate(end_details):
            if x.text.strip() == "Referee:":
                js["Referee"] = name_detils[j].text.strip()
                j = j + 1
            if x.text.strip() == "Venue:":
                js["Venue"] = name_detils[j].text.strip()
                j = j + 1
            if x.text.strip() == "Attendance:":
                js["Attendance"] = name_detils[j].text.strip()
                j = j + 1
    except:
        print(f" No additional match details.", end="\r")
        return js

    return js


#################################### WRITE DATA #########################################
def write_data(data, filename="flash_data.xlsx"):

    df = pd.DataFrame.from_records(data)
    df2 = df[
        [
            "_id",
            "date",
            "tournament",
            "home_team",
            "away_team",
            "home_goals",
            "away_goals",
            "H_G1",
            "H_G2",
            "H_G3",
            "H_G4",
            "H_G5",
            "H_G6",
            "H_G7",
            "H_G8",
            "H_G9",
            "H_G10",
            "H_Y1",
            "H_Y2",
            "H_Y3",
            "H_Y4",
            "H_Y5",
            "H_Y6",
            "H_Y7",
            "H_Y8",
            "H_Y9",
            "H_Y10",
            "H_R1",
            "H_R2",
            "H_R3",
            "H_R4",
            "H_R5",
            "H_YR1",
            "H_YR2",
            "H_YR3",
            "H_YR4",
            "H_YR5",
            "A_G1",
            "A_G2",
            "A_G3",
            "A_G4",
            "A_G5",
            "A_G6",
            "A_G7",
            "A_G8",
            "A_G9",
            "A_G10",
            "A_Y1",
            "A_Y2",
            "A_Y3",
            "A_Y4",
            "A_Y5",
            "A_Y6",
            "A_Y7",
            "A_Y8",
            "A_Y9",
            "A_Y10",
            "A_R1",
            "A_R2",
            "A_R3",
            "A_R4",
            "A_R5",
            "A_YR1",
            "A_YR2",
            "A_YR3",
            "A_YR4",
            "A_YR5",
            "Referee",
            "Venue",
            "Attendance",
        ]
    ].copy()

    df2["url"] = df2["_id"].apply(
        lambda x: f"https://www.flashscore.co.uk/match/{x}/#/match-summary/match-summary"
    )
    df2["date"] = pd.to_datetime(df2["date"], format="%d.%m.%Y %H:%M")
    df2["date"] = df2["date"].dt.strftime("%Y-%m-%d %H:%M")
    df2 = df2.set_index("_id")

    try:
        with pd.ExcelWriter(
            filename, engine="openpyxl", mode="a", if_sheet_exists="overlay"
        ) as writer:
            df2.to_excel(
                writer,
                sheet_name="summary_stats",
                startrow=writer.sheets["summary_stats"].max_row,
                header=False,
            )
    except FileNotFoundError:
        # If the file does not exist, create a new one
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            df2.to_excel(writer, sheet_name="summary_stats")
    except Exception as e:
        print(f"Error inside pandas to excel writing: {e}")
        sys.exit(1)

    return df2


#################################### GET INPUT #########################################
def remove_years(urls):
    bl = [str(i) for i in range(1970, 2020)]
    for x in bl:
        for url in urls:
            if x in url:
                urls.remove(url)
    return urls


def validate_input(inp, nb):
    if inp == "q" or inp == "quit":
        sys.exit("Exiting.")
    inp = int(inp) if inp.isdigit() else False
    return inp if inp and 0 < inp <= nb else False


def get_input():
    tour = lambda x: " ".join(x.split("/")[4:-1]) if "/" in x else x
    while not (idx := None):
        for i, x in enumerate(league_urls, 1):
            print(f"{i:>2}) {tour(x)}")
        idx = input(">>> ")
        idx = validate_input(idx, len(league_urls))
        if idx:
            break
    url = league_urls[int(idx) - 1]

    if url == "Sync whole history":
        sys.exit("TBI")
    if url == "Update latest season":
        match_urls = []
        match_urls.extend(get_matches_per_season(league_urls[:-2], 1))
        match_urls = filter_urls(match_urls)
        return match_urls

    print(f"{idx}) Loading... {url}")

    season_soup = (
        get_soup(url + "archive/").find(id="tournament-page-archiv").find_all("a")
    )
    season = lambda x: " ".join(x.split("/")[4:-2]) if "/" in x else x
    seasons = [
        f"https://www.flashscore.co.uk{x.get('href')}results/"
        for x in season_soup
        if "football" in x.get("href")
    ]
    seasons = remove_years(seasons)
    seasons.reverse()
    seasons.extend(["All seasons"])
    while not (idx := None):
        for i, x in enumerate(seasons, 1):
            print(f"{i:>2}) {season(x)}")
        idx = input(">>> ")
        idx = validate_input(idx, len(seasons))
        if idx:
            break
    url = seasons[int(idx) - 1]

    if url == "All seasons":
        match_urls = []
        match_urls.extend(get_matches_per_season(seasons[:-1]), 0)
        match_urls = filter_urls(match_urls)
        return match_urls

    print(f"{idx:>2}) {season(url)} {url}")

    match_urls = get_matches_per_season([url])
    match_urls = filter_urls(match_urls)
    return match_urls


def filter_urls(match_urls, filename="flash_data.xlsx"):
    try:
        with pd.ExcelFile(filename) as reader:
            sheet_1 = pd.read_excel(reader, sheet_name="summary_stats")
        done_urls = list(sheet_1["_id"])
    except FileNotFoundError:
        print(f'File "{filename}" not found. Proceeding with all match URLs.')
        return match_urls
    except Exception as e:
        print(f"Error reading excel file: {e}")
        sys.exit(1)

    d_urls = [
        f"https://www.flashscore.co.uk/match/{_id}/#/match-summary/match-summary"
        for _id in done_urls
    ]
    todo_urls = list(set(match_urls) - set(d_urls))
    return todo_urls


def new_func(e):
    sys.exit('Error reading "excel file".', e)


#################################### MAIN FUNCTION #########################################
match_urls = get_input()
print(f" [*] {len(match_urls)} new matches found")
##
data = match_summary(match_urls)
##
if data:
    df = write_data(data)
print(f" {len(data)} new matches added.")
##
