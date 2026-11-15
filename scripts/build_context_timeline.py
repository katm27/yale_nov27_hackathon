import json

P = []
def add(fr, to, title, text, links, sources):
    d = {"from": fr, "to": to, "title": title, "text": text}
    if links:
        d["links"] = links
    d["sources"] = [{"label": l, "url": u} for l, u in sources]
    P.append(d)

add("2018-01", "2018-06", "Hunger peaks as a ceasefire is agreed",
    "On 26 February 2018, the Food and Agriculture Organization (FAO), UNICEF and the World Food Programme (WFP) warned that more than 7 million people, almost two-thirds of the population, could become severely food insecure during the May–July lean season. Between 16 April and 24 May, government and aligned forces attacked villages in Leer and Mayendit counties, Unity, and the UN documented at least 232 civilians killed. On 27 June, President Salva Kiir and opposition leader Riek Machar signed the Khartoum Declaration, which committed them to a permanent ceasefire within 72 hours.",
    "The civilians-killed chart shows 563 civilians killed in attacks in 2018 (ACLED), and the aid appeal was 70% funded that year.",
    [("UNICEF/FAO/WFP, Nearly two-thirds of the population at risk of rising hunger, 26 Feb 2018", "https://www.unicef.org/press-releases/population-south-sudan-risk-rising-hunger"),
     ("UN News, 'Horrific acts' by government may constitute war crimes, 10 Jul 2018", "https://news.un.org/en/story/2018/07/1014331"),
     ("Radio Tamazuj, Official text: Khartoum Declaration of Agreement, Jun 2018", "https://radiotamazuj.org/en/news/article/official-text-khartoum-declaration-of-agreement")])

add("2018-07", "2018-12", "Peace deal signed; Machar returns to Juba",
    "At the peak of the July–August lean season, 6.1 million people, nearly 60% of the population, were in Crisis-level hunger or worse on the Integrated Food Security Phase Classification (IPC) scale. The revitalised peace agreement was signed in September. On 31 October 2018, Riek Machar returned to Juba for the first time since fleeing in July 2016, to attend a peace celebration.",
    "The radar flood chart shows 2018 as the low baseline year, with a mean monthly flooded area of about 3.2k km².",
    [("UNICEF/FAO/WFP, Conflict pushes South Sudanese into hunger, 28 Sep 2018", "https://www.unicef.org/press-releases/conflict-pushes-south-sudanese-hunger-more-6-million-people-face-desperate-food"),
     ("Al Jazeera, South Sudan rebel leader Machar back in Juba after two years, 31 Oct 2018", "https://www.aljazeera.com/news/2018/10/31/south-sudan-rebel-leader-machar-back-in-juba-after-two-years/")])

add("2018-09", "2018-09", "Revitalised peace agreement (R-ARCSS) signed",
    "On 12 September 2018 in Addis Ababa, President Salva Kiir, Riek Machar and other parties signed the Revitalised Agreement on the Resolution of the Conflict in the Republic of South Sudan (R-ARCSS). It was signed at a summit of the regional bloc IGAD and revived the 2015 peace deal, which had collapsed. It set an eight-month pre-transitional period, followed by a 36-month transitional period under a unity government.",
    None,
    [("Anadolu Agency, South Sudanese warring parties agree to share power, 12 Sep 2018", "https://aa.com.tr/en/africa/south-sudanese-warring-parties-agree-to-share-power/1253348"),
     ("ACCORD, Reviving peace in South Sudan through the Revitalised Peace Agreement", "https://www.accord.org.za/conflict-trends/reviving-peace-in-south-sudan-through-the-revitalised-peace-agreement/")])

add("2019-01", "2019-06", "Unity government delayed six months",
    "On 22 February 2019, the World Food Programme said nearly 7 million people could face acute food insecurity at the height of the May–July lean season. On 3 May 2019, the parties met in Addis Ababa and agreed to delay forming the unity government by six months from 12 May. The opposition said security arrangements had to be resolved first.",
    "The food insecurity chart shows that in 2019, on average, 53% of each county's population was at IPC Crisis level or worse.",
    [("WFP, Increasing number of people face severe food shortages in South Sudan, 22 Feb 2019", "https://www.wfp.org/news/increasing-number-people-face-severe-food-shortages-south-sudan"),
     ("Al Jazeera, South Sudan rivals agree to delay forming government, 3 May 2019", "https://www.aljazeera.com/news/2019/5/3/south-sudan-rivals-agree-to-delay-forming-government")])

add("2019-07", "2019-12", "Severe floods; second delay to unity government",
    "Severe flooding began in July 2019. By 25 October, the UN Office for the Coordination of Humanitarian Affairs (OCHA) estimated that 908,000 people were affected in 32 counties across seven states, including Jonglei, Upper Nile and Unity. On 7 November in Entebbe, Uganda, Kiir and Machar agreed to delay forming the unity government by a further 100 days from 12 November.",
    "The radar flood chart shows the mean monthly flooded area nearly doubling, from 3.2k km² in 2018 to 6.2k km² in 2019. The civilians-killed chart shows 983 civilians killed in attacks in 2019 (ACLED).",
    [("Al Jazeera, UN: Almost one million people affected by floods in South Sudan, 25 Oct 2019", "https://www.aljazeera.com/news/2019/10/25/un-almost-one-million-people-affected-by-floods-in-south-sudan/"),
     ("The EastAfrican, S. Sudan warring parties agree to delay unity government by 100 days, Nov 2019", "https://theeastafrican.co.ke/tea/news/east-africa/s-sudan-warring-parties-agree-to-delay-unity-government-by-100-days-1430542")])

add("2020-01", "2020-06", "Unity government formed; violence in Jonglei",
    "On 22 February 2020, Riek Machar was sworn in as First Vice President and the Revitalised Transitional Government of National Unity (R-TGoNU) was formed. South Sudan confirmed its first COVID-19 case on 5 April. In the first half of 2020, community-based militias attacked villages across Jonglei and the Greater Pibor Administrative Area (GPAA). A UN human rights report found that more than 738 people were killed and at least 686 women and children were abducted.",
    "The sexual violence chart lists 30 reported conflict-related incidents in 2020 (Insecurity Insight). Reporting is very incomplete.",
    [("UPI, South Sudan president again names rebel as deputy in power-sharing agreement, 22 Feb 2020", "https://www.upi.com/Top_News/World-News/2020/02/22/South-Sudan-president-again-names-rebel-as-deputy-in-power-sharing-agreement/2131582384234/"),
     ("WHO Africa, South Sudan confirms first case of COVID-19, Apr 2020", "https://afro.who.int/fr/node/12499"),
     ("UN News, Allies of South Sudan militias must be held accountable, 15 Mar 2021", "https://news.un.org/en/story/2021/03/1087352")])

add("2020-07", "2020-12", "Second year of major floods; famine likely in Pibor",
    "From July 2020 to January 2021, the UN Office for the Coordination of Humanitarian Affairs (OCHA) estimated that flooding affected about 1,066,000 people. Jonglei and the Greater Pibor Administrative Area were the worst hit. In December 2020, the Famine Review Committee of the Integrated Food Security Phase Classification (IPC) classified parts of western Pibor County as 'Famine Likely'. The government did not endorse the finding.",
    "The flood charts show about 475k people displaced by flooding in 2020 (IOM) and a mean monthly flooded area of 9.7k km². The aid appeal was 65% funded that year.",
    [("OCHA/ICCG, South Sudan Flooding Situation Report, 31 Jan 2021", "https://docs.southsudanngoforum.org/sites/default/files/2021-02/south_sudan_flooding_situation_report_31jan2021_1.pdf"),
     ("IPC, Famine Review Committee: Pibor County, South Sudan, Dec 2020", "https://www.fsinplatform.org/sites/default/files/resources/files/IPC_South_Sudan_Famine_Review_2020Nov.pdf"),
     ("AP via KSAT, New report says part of South Sudan is in 'likely famine', 11 Dec 2020", "https://www.ksat.com/news/world/2020/12/11/new-report-says-part-of-south-sudan-is-in-likely-famine/")])

add("2021-01", "2021-06", "Record hunger projected; parliament reconstituted",
    "An Integrated Food Security Phase Classification (IPC) analysis released in December 2020 projected that 7.24 million people, 60% of the population, would face Crisis-level hunger or worse in April–July 2021. On 8 May 2021, President Kiir dissolved the national legislature. On 10 May, he reconstituted the Transitional National Legislative Assembly with 550 members, as the peace agreement required.",
    "The funding chart shows US humanitarian funding of $792M in 2021 (OCHA FTS), and the aid appeal was 73% funded that year.",
    [("UN News, IPC projects 7.24 million facing food crisis in South Sudan, 18 Dec 2020", "https://news.un.org/en/story/2020/12/1080432"),
     ("Peace Accords Matrix (Kroc Institute), Transitional power-sharing government – 2021", "https://peaceaccords.nd.edu/implementation/transitional-powersharing-government-2021")])

add("2021-07", "2021-12", "Tambura violence, opposition split, worst recorded floods",
    "From June to September 2021, fighting between armed groups in Tambura County, Western Equatoria, killed at least 440 civilians and displaced about 80,000 people, according to a UN human rights report. In early August, General Simon Gatwech Dual's faction announced in the Kitgwang Declaration that Riek Machar had been removed as head of the armed opposition, the Sudan People's Liberation Movement/Army-in-Opposition (SPLM/A-IO), and the two sides clashed. The UN Office for the Coordination of Humanitarian Affairs (OCHA) reported that flooding affected more than 835,000 people from May onward, the worst flooding on record.",
    "The flood charts show about 475k people displaced by flooding in 2021 (IOM) and a mean monthly flooded area of 10.0k km². The civilians-killed chart shows 1,783 civilians killed in attacks in 2021 (ACLED).",
    [("Radio Tamazuj, UNMISS: Hundreds of killings among grave violations against civilians in Tambura, Mar 2022", "https://radiotamazuj.org/en/news/article/unmiss-hundreds-of-killings-among-grave-violations-committed-against-civilians-in-tambura"),
     ("Radio Tamazuj, Machar still in control of SPLM/A-IO, rubbishes Gen. Gatwech and group, Aug 2021", "https://radiotamazuj.org/en/news/article/machar-still-in-control-of-splm-a-io-rubbishes-gen-gatwech-and-group"),
     ("UN News, Dire impact of floods in South Sudan as new wet season looms, 29 Mar 2022", "https://news.un.org/en/story/2022/03/1114992")])

add("2022-01", "2022-06", "Highest hunger levels; attacks in southern Unity",
    "An Integrated Food Security Phase Classification (IPC) analysis released in April 2022 projected that 7.74 million people, 62.7% of the population, would face Crisis-level hunger or worse in April–July 2022. About 87,000 of them would be in Catastrophe (IPC Phase 5), in parts of Jonglei, the Greater Pibor Administrative Area, Lakes and Unity. From February to May 2022, attacks in Koch, Leer and Mayendit counties of Unity killed about 173 civilians and displaced about 44,000 people, according to the UN. The UN attributed most of these attacks to government forces and allied militias.",
    "The food insecurity chart shows that in 2022, on average, 54% of each county's population was at IPC Crisis level or worse. The civilians-killed chart shows 1,907 civilians killed in attacks in 2022 (ACLED), the highest in the series.",
    [("UNICEF/FAO/WFP, UN agencies call for scaled-up response to increasing hunger and malnutrition, Apr 2022", "https://www.unicef.org/press-releases/un-agencies-call-scaled-response-address-increasing-hunger-and-malnutrition-south"),
     ("UN News, UN report on attacks on civilians in southern Unity State, 6 Sep 2022", "https://news.un.org/en/story/2022/09/1126091"),
     ("UNMISS/OHCHR, Report on attacks on civilians in southern Unity State, 6 Sep 2022", "https://unmiss.unmissions.org/sites/default/files/report_on_attacks_on_civilians_in_southern_unity_state_-_06_september_2022.pdf")])

add("2022-07", "2022-12", "Transition extended; fighting in Upper Nile; fourth year of floods",
    "In August 2022, the transitional government adopted a roadmap that extended the transitional period by 24 months and moved elections from early 2023 to December 2024. From 14 to 15 August, armed factions fought in Tonga, Panyikang County, Upper Nile, and thousands of people fled toward Malakal. By October, according to the World Health Organization (WHO) and the UN Office for the Coordination of Humanitarian Affairs, severe flooding had affected more than 1 million people in 36 counties and the Abyei Administrative Area, the fourth year in a row of extreme floods.",
    "The flood charts show about 416k people displaced by flooding in 2022 (IOM) and a mean monthly flooded area of 10.1k km². The Sudd wetland's flooded area was about four times its 2018 size. USAID paid out $1.10B in 2022, and the US provided 59% of all humanitarian funding.",
    [("International IDEA, Democracy Tracker: South Sudan, August 2022", "https://idea.int/democracytracker/report/south-sudan/august-2022"),
     ("OCHA, Tonga clashes: Flash Update No. 1, 19 Aug 2022", "https://reliefweb.int/report/south-sudan/tonga-clashes-flash-update-no-1-19-august-2022"),
     ("WHO, South Sudan humanitarian situation report, Issue 10, Oct 2022", "https://www.afro.who.int/sites/default/files/2022-11/South%20Sudan%20humanitarian%20sitrep_Issue%20%2310_October%202022.pdf")])

add("2023-01", "2023-06", "Lean-season hunger; deadly clashes in Malakal PoC site",
    "An Integrated Food Security Phase Classification (IPC) analysis released in November 2022 projected that 7.76 million people, about two-thirds of the population, would face Crisis-level hunger or worse in April–July 2023. About 43,000 of them would be in Catastrophe (IPC Phase 5). After a killing on 7 June, clashes broke out between Shilluk and Nuer residents of the UN Protection of Civilians (PoC) site in Malakal. The UN Mission in South Sudan (UNMISS) verified at least 14 people killed and 28 injured; 6,000–7,000 Nuer residents then left the site.",
    "The aid appeal chart shows the 2023 appeal 56% funded, the lowest of any year from 2018 to 2023.",
    [("WFP/FAO/UNICEF, Hunger and malnutrition being driven by climate crisis and conflict in South Sudan, 3 Nov 2022", "https://www.wfp.org/news/hunger-and-malnutrition-being-driven-climate-crisis-and-conflict-south-sudan"),
     ("UNMISS, Statement by SRSG Nicholas Haysom to the Security Council, 20 Jun 2023", "https://unmiss.unmissions.org/en/node/23401")])

add("2023-04", "2023-04", "War in Sudan begins",
    "On 15 April 2023, war broke out in Sudan between the Sudanese Armed Forces and the paramilitary Rapid Support Forces (RSF). Within weeks, tens of thousands of people crossed into South Sudan at the Joda border point in Renk County, Upper Nile. Most were South Sudanese returning home, many of whom had been refugees in Sudan.",
    "The displacement chart shows about 396k arrivals fleeing the Sudan war in 2023 (IOM).",
    [("UNHCR, Sudan violence forces South Sudanese refugees to return to the country they fled, May 2023", "https://www.unhcr.org/us/news/stories/sudan-violence-forces-south-sudanese-refugees-return-country-they-fled"),
     ("UNHCR, One year of war in Sudan and impact on South Sudan (press briefing), 9 Apr 2024", "https://www.unognewsroom.org/story/en/2130/one-year-of-war-in-sudan-and-impact-on-south-sudan-unhcr-09-april-2024")])

add("2023-07", "2023-12", "Arrivals from Sudan overwhelm border transit sites",
    "People fleeing Sudan kept arriving through Renk. In September 2023, UNHCR, the UN refugee agency, reported that the Renk transit centre, built for 3,000 people, held more than 8,000. An Integrated Food Security Phase Classification (IPC) analysis released on 7 November 2023 projected that 7.1 million people would face Crisis-level hunger or worse in April–July 2024. About 79,000 of them would be in Catastrophe, in Pibor, Aweil East and among returnees from Sudan.",
    "The displacement charts show about 396k arrivals from the Sudan war in 2023 (IOM). Forced travellers counted by IOM flow monitoring rose from 25k in 2022 to 111k in 2023.",
    [("UNHCR, As more people flee conflict in Sudan, conditions at South Sudan border deteriorate, Sep 2023", "https://www.unhcr.org/news/stories/more-people-flee-conflict-sudan-conditions-south-sudan-border-deteriorate"),
     ("Radio Tamazuj, Over 7.1 million South Sudanese will face food crisis in 2024, 7 Nov 2023", "https://radiotamazuj.org/en/news/article/over-7-1-million-south-sudanese-will-face-food-crisis-in-2024")])

add("2024-01", "2024-06", "Oil export pipeline disrupted; Sudan arrivals continue",
    "In early February 2024, the pipeline carrying South Sudan's oil exports through Sudan was damaged in White Nile State, an area held by the paramilitary Rapid Support Forces (RSF). Fighting prevented repairs, and the International Crisis Group said the pipeline carried two-thirds to three-quarters of oil revenue. In May 2024, Kenya launched the Tumaini Initiative, talks between the government and groups that had not signed the 2018 agreement. By June 2024, more than 680,000 people had arrived from Sudan since April 2023.",
    "The displacement chart shows about 195k arrivals from the Sudan war in 2024 (IOM).",
    [("Al Jazeera, South Sudan on the brink after oil exports derailed by Sudan's civil war, 26 Mar 2024", "https://www.aljazeera.com/features/2024/3/26/south-sudan-on-the-brink-after-oil-exports-derailed-by-sudans-civil-war"),
     ("UNMISS, Tumaini peace talks between Government and hold-out groups resume in Nairobi, 5 Dec 2024", "https://unmiss.unmissions.org/en/node/23812"),
     ("MSF, Sudan war is exacerbating humanitarian needs in neighbouring South Sudan, 18 Jun 2024", "https://www.doctorswithoutborders.ca/sudan-war-is-exacerbating-humanitarian-needs-in-neighbouring-south-sudan-warns-msf/")])

add("2024-07", "2024-12", "Elections postponed; floods and cholera",
    "On 13 September 2024, the presidency postponed elections planned for December 2024 to 22 December 2026 and extended the transitional period by two years, citing unfinished preparations such as the census and a permanent constitution. In early November, the UN Office for the Coordination of Humanitarian Affairs (OCHA) reported that about 1.4 million people were affected by flooding in 43 counties and Abyei, and more than 379,000 were displaced. A cholera outbreak began in Renk with a first suspected case on 28 September, and the Ministry of Health declared it in late October.",
    "The flood charts show about 360k people displaced by flooding in 2024 (IOM) and a mean monthly flooded area of 9.1k km². The US provided 50% of all humanitarian funding in 2024.",
    [("AP via ABC News, South Sudan postpones December elections by 2 years, 13 Sep 2024", "https://abcnews.go.com/International/wireStory/south-sudan-postpones-december-elections-2-years-citing-113677325"),
     ("Al Jazeera, Nearly 380,000 people displaced by South Sudan floods, UN says, 9 Nov 2024", "https://www.aljazeera.com/news/2024/11/9/nearly-380000-people-displaced-by-south-sudan-floods-un-says"),
     ("WHO Africa, Cholera in South Sudan: One Year On (factsheet), Oct 2025", "https://www.afro.who.int/sites/default/files/2025-10/Knowledge%20Management%20Series%20for%20Health-%20Cholera%20in%20South%20Sudan%3B%20One%20Year%20On%20Factsheet..pdf")])

add("2025-01", "2025-06", "US aid cuts, airstrikes and famine risk",
    "After the US cut foreign aid in early 2025, Save the Children reported that seven of the 27 health centres it supported in Jonglei closed, and that eight people, including five children, died in March while walking to seek cholera treatment after a US-funded transport service shut down. On 3 May, aircraft bombed a hospital run by Médecins Sans Frontières (MSF) in Old Fangak, Jonglei; Radio Tamazuj reported that the planes belonged to the South Sudan People's Defence Forces (SSPDF) and that four civilians were killed. On 12 June, an Integrated Food Security Phase Classification (IPC) update found 7.7 million people, 57% of the population, in Crisis-level hunger or worse, with Nasir and Ulang counties in Upper Nile at risk of famine.",
    "The funding charts show US humanitarian funding falling to $282M in 2025 (31% of the total), USAID payouts falling from $681M in 2024 to $287M, and new USAID commitments of $152M. IOM recorded about 337k people displaced by national-level conflict in 2025, compared with 7k in 2024.",
    [("Al Jazeera, South Sudanese children die as US aid cuts shutter medical services: NGO, 9 Apr 2025", "https://www.aljazeera.com/news/2025/4/9/us-aid-cuts-leave-south-sudan-children-dead-as-medical-services-collapse"),
     ("Radio Tamazuj, 4 civilians killed as SSPDF planes bomb MSF hospital in Old Fangak, 3 May 2025", "https://www.radiotamazuj.org/en/news/article/4-civilians-killed-as-sspdf-planes-bomb-msf-hospital-in-old-fangak"),
     ("UNICEF/FAO/WFP, Conflict, displacement and disease drive food insecurity and malnutrition to alarming levels, 12 Jun 2025", "https://www.unicef.org/press-releases/conflict-displacement-and-disease-drive-food-insecurity-and-malnutrition-alarming")])

add("2025-03", "2025-03", "Nasir fighting, aerial bombing and Machar's detention",
    "On 4 March 2025, armed Nuer youth known as the White Army attacked the army base in Nasir, Upper Nile. On 7 March, a UN helicopter evacuating soldiers from Nasir came under fire, and one UN crew member was killed. Between 16 and 21 March, Human Rights Watch documented government air attacks with improvised incendiary weapons in Nasir, Longechuk and Ulang counties that killed at least 58 people. On 26 March, security forces surrounded First Vice President Riek Machar's residence in Juba and placed him under house arrest.",
    "The displacement chart shows about 337k people displaced by national-level conflict in 2025 (IOM), compared with 7k in 2024.",
    [("Radio Tamazuj, SSPDF commander, UN crew killed in Nasir, 7 Mar 2025", "https://www.radiotamazuj.org/en/news/article/sspdf-commander-un-crew-killed-in-nasir"),
     ("Human Rights Watch, South Sudan: Incendiary bombs kill, burn civilians, 9 Apr 2025", "https://www.hrw.org/news/2025/04/09/south-sudan-incendiary-bombs-kill-burn-civilians"),
     ("Human Rights Watch, South Sudan: Ensure due process, fair trials of opposition, 15 Sep 2025", "https://www.hrw.org/news/2025/09/15/south-sudan-ensure-due-process-fair-trials-of-opposition")])

add("2025-07", "2025-12", "Machar charged and tried; floods return",
    "On 11 September 2025, the justice minister announced charges including murder, treason and crimes against humanity against 21 people, among them Riek Machar. The charges relate to the March attack in Nasir, and the same day President Kiir suspended Machar as First Vice President. Machar's trial opened before a special court in Juba on 22 September, and his party, the Sudan People's Liberation Movement-in-Opposition (SPLM-IO), called the charges politically motivated. By 13 November, the UN Office for the Coordination of Humanitarian Affairs (OCHA) reported that flooding had affected about 1.35 million people in 39 counties and displaced about 375,600.",
    "The aid appeal chart shows the 2025 appeal 46% funded ($787M of $1.70B), the lowest in the series. IOM recorded about 242k people displaced by flooding in 2025, and the mean monthly flooded area was 9.3k km².",
    [("Human Rights Watch, South Sudan: Ensure due process, fair trials of opposition, 15 Sep 2025", "https://www.hrw.org/news/2025/09/15/south-sudan-ensure-due-process-fair-trials-of-opposition"),
     ("Arab News (AFP), South Sudan opposition figure Riek Machar appears in court on treason charges, Sep 2025", "https://www.arabnews.pk/node/2616243"),
     ("OCHA, South Sudan: Floods snapshot, 13 Nov 2025", "https://reliefweb.int/report/south-sudan/south-sudan-floods-snapshot-13-november-2025")])

out = "/home/user/yale_nov27_hackathon/docs/data/context_timeline.json"
with open(out, "w") as f:
    json.dump({"periods": P}, f, indent=2, ensure_ascii=False)
print(len(P))
