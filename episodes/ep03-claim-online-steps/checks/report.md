# Check report · ep03-claim-online-steps

Checked commit `8408af3` on 2026-11-14 16:27 UTC. GitHub writes a new report after every upload.

**RESULT: POSTED** · This reel is live: https://www.instagram.com/reel/DfttMyBvNKx/ (posted 2026-11-14). Never post it again, and don't change its files: anything below is for a person.

## For a person

1. **Fact · final_wait_months** · fact 'final_wait_months' needs a person to check the source. Gazette pp. 90–91: a member isn't eligible 'unless the member has not been employed ... for a continuous period of not less than twelve months immediately preceding the date of application'. The old 1952 Scheme said 2 months. Exceptions in para 49(1) and the second proviso (marriage) don't change the reel's case. No wait at all on retirement after 55, permanent incapacity, migration abroad, retrenchment or voluntary retirement (para 49(1)), or for a woman resigning to marry (second proviso).
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps final_wait_months --by NAME`. Muse never marks a fact checked.
2. **Fact · settle_days** · fact 'settle_days' needs a person to check the source. Gazette p. 94: a claim complete in all respects 'shall be settled and the benefit amount paid to the beneficiaries within twenty days from the date of receipt by the Commissioner.' (It was paragraph 72(7) in the 1952 Scheme.)
   - A person opens the source, finds the number and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps settle_days --by NAME`. Muse never marks a fact checked.
3. **Rule · services_free** · rule 'services_free' needs a person to check the source. Quote: 'All EPFO services including claim filing, transfers, KYC updation, and grievance process are entirely free of cost and members should not pay any fees to third party agents or cyber cafes for services that can be easily accessed online.'
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps services_free --by NAME`. Muse never marks a rule checked.
4. **Rule · grievance_epfigms** · rule 'grievance_epfigms' needs a person to check the source. Open it: 'Register Grievance', for PF members, pensioners and employers; the site says 'EPFiGMS is available in UMANG.'
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps grievance_epfigms --by NAME`. Muse never marks a rule checked.
5. **Rule · portal_login** · rule 'portal_login' needs a person to check the source. Open the page: the box asks for 'UAN Number', 'Password' and a captcha, and the button says 'Sign in'. The page also says 'Do not share passwords.' Whether an OTP follows 'Sign in' isn't on an official page: see it on your own login.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps portal_login --by NAME`. Muse never marks a rule checked.
6. **Rule · online_claim_kyc** · rule 'online_claim_kyc' needs a person to check the source. Gazette p. 80, para 25(1): the member furnishes 'Aadhaar Number ..., an Aadhaar seeded Bank account number ..., the Permanent account Number ... and the Universal Account Number.' PIB 1 May 2017 (https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=161420): members 'who have activated their UAN and seeded their KYC (Aadhaar) with EPFO will be able to apply for PF final settlement (form19), Pension withdrawal benefit (Form10-C) and PF part withdrawal (Form31)'.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps online_claim_kyc --by NAME`. Muse never marks a rule checked.
7. **Rule · bank_verified** · rule 'bank_verified' needs a person to check the source. Quote: 'the role of Employer to approve the verification of bank account has now been dispensed with in the seeding process of the member's Bank Account.' The same release: EPFO 'has completely dispensed with the requirement of uploading an image of a cheque leaf or attested bank passbook while filing online claims.' (EPFO's 2017 FAQ, seen only in a search snippet: payment goes 'only into the Bank Account registered with EPFO'.)
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps bank_verified --by NAME`. Muse never marks a rule checked.
8. **Rule · exit_needed** · rule 'exit_needed' needs a person to check the source. Gazette p. 79, para 24 (clause (v), renumbered (5) by the correction notice of 4 August 2026): 'Every employer shall, within fifteen days of the close of each month, upload electronically on the designated portal details of the employees leaving the service'. PIB 19 Jan 2025 (https://www.pib.gov.in/PressReleasePage.aspx?PRID=2094229): members whose UAN is validated through Aadhaar 'can update their profile like ... date of joining and date of leaving themselves without the requirement of uploading any document'.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps exit_needed --by NAME`. Muse never marks a rule checked.
9. **Rule · claim_menu** · rule 'claim_menu' needs a person to check the source. Quote: 'a. Login to Member Interface of Unified Portal. b. Go to Online Services>>Claim (Form-31,19,10C & 10D). c. Enter last 4 digits of your Bank Account and verify d. Click on "Proceed for Online Claim"'. The research saw this only in a search snippet (epfo.gov.in refused automated requests) and found nothing newer, and EPFO upgraded its systems in June 2026: check every name on your own login while taking the screenshots. GitHub also reads the screenshots and fails one that doesn't show these names.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps claim_menu --by NAME`. Muse never marks a rule checked.
10. **Rule · claim_choice** · rule 'claim_choice' needs a person to check the source. PIB 2017 names the online claims: 'PF final settlement (form19), Pension withdrawal benefit (Form10-C) and PF part withdrawal (Form31)', and 'They are not required to give any supporting document'. EPFO's April 2020 FAQ (https://www.epfindia.gov.in/site_docs/PDFs/Updates/covid_faq_claim_04042020.pdf, seen in a search snippet) has the member pick 'PF Advance (Form 31)' from a list, then give the purpose, amount and address. Gazette pp. 87–88, para 46: an advance is for illness, education, marriage, housing or special circumstances. Check the list's wording on your own login.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps claim_choice --by NAME`. Muse never marks a rule checked.
11. **Rule · aadhaar_otp** · rule 'aadhaar_otp' needs a person to check the source. Quote: 'Members applying online are required to authenticate their claim submission using OTP sent to their UIDAI registered Mobile number'. The 2020–21 FAQ (https://www.epfindia.gov.in/site_docs/PDFs/Circulars/Y2020-2021/FAQUANKYC.pdf): 'At the time of claim submission, OTP is sent to Aadhaar linked mobile only.' Both seen in search snippets: check the button ('Get Aadhaar OTP' in 2020) on your own login.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps aadhaar_otp --by NAME`. Muse never marks a rule checked.
12. **Rule · track_status** · rule 'track_status' needs a person to check the source. Quote: 'track the status of the transfer claim submitted by going to 'Online Services' tab and then to 'Track Claim Status'.' (seen in a search snippet). PIB 21 Nov 2024 (https://www.pib.gov.in/PressReleasePage.aspx?PRID=2075422): an activated UAN lets members 'submit online claims ... and track claims in real time.' Check the menu name on your own login.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps track_status --by NAME`. Muse never marks a rule checked.
13. **Rule · ineligible_claims** · rule 'ineligible_claims' needs a person to check the source. Quote: 'Certain upfront validations have been developed to guide members about eligibility /admissibility of claims so as to ensure that members do not file ineligible claims'. ep01's sources (PIB 14 June 2024, PRID 2025221) say EPFO returns incomplete claims and rejects ineligible ones.
   - A person opens the source, finds the rule and records it with `python3 tools/approve.py fact episodes/ep03-claim-online-steps ineligible_claims --by NAME`. Muse never marks a rule checked.
14. **Voice · S03** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: लोग एजेंट को फ़ीस देते हैं। या गलत फ़ॉर्म चुनते हैं। · heard: लोग एजेंट को फईज देते हैं या गलत फाम चुनते हैं.
15. **Voice · S06** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: एक: यूएएन आधार से जुड़ा। दो: बैंक अकाउंट केवाईसी में वेरिफ़ाइड। तीन: नौकरी छोड़ी, तो एग्ज़िट डेट मार्क्ड। · heard: 1. UN आधार से जुड़ा 2. BANK ACCOUNT KYC में वेरिफाइड 3. नौकरी छोडी तो EXIT DATE माक्ट
16. **Voice · S07** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: मेंबर पोर्टल पे यूएएन और पासवर्ड से लॉगिन करो। · heard: मेंबर पोटल पे यूएन और पास्वर्ड से लोगिन करो
17. **Voice · S09** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: बैंक अकाउंट का नंबर डालो, और वेरिफ़ाई दबाओ। · heard: बैंक अकांट का नम्बर डालो और वेरिफाई दबाओ।
18. **Voice · S11** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: लिस्ट में अपना क्लेम फ़ॉर्म चुनो। · heard: लिस्ट में अपना क्लेम फौम चुनो
19. **Voice · S13** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: आधार वाले मोबाइल पे ओटीपी आएगा, डालो और सबमिट। · heard: आधार वाले मोबाईल पे OTP आएगा, डालो और सब्मिट।
20. **Voice · S14** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: फ़ॉर्म चुनने से पहले ये देखो। · heard: फॉर्म चुनने से पहले ये देखो।
21. **Voice · S15** · heard 918, which isn't in the line, so a word may be misread; almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: नौकरी छोड़े बारह महीने हुए? पूरा पीएफ: फ़ॉर्म नाइनटीन। नौकरी चालू है? एडवांस: फ़ॉर्म थर्टी वन। · heard: नौक्री छोडे 12 महिने हुए पूरा P.F. फॉरम 918 नौक्री चालू है एद्वान्स फॉरम 31
22. **Voice · S17** · almost no pause at the start: check the first word isn't clipped
   - A person listens to this line.
   - should say: बीस दिन में पैसा ना आए? ईपीएफ़आईजीएमएस पे शिकायत करो। · heard: बीस दिन में पैसा ना आए इपी एफाई जीमेस पे शिकायत करो

## To look at (Muse, not blocking)

OCR can't read symbols, lone digits or handwriting. Look at these in the reel and say in your report that they're right.
- `→` (too short or only symbols; check by eye)
- `↘` (too short or only symbols; check by eye)
- `↗` (too short or only symbols; check by eye)

## Approvals

Steps waiting for a person's approval (recorded with `tools/approve.py step`): 01-brief, 02-data, 03-script.

## Notes

- Script E3.3: estimated length 70 s and the shot timeline 94 s differ by more than 5 s

## Passed

- Episode file: brief, data, script, shots and post
- Not a repeat: topic, hook, script and photos are this reel's own (TOPICS.md)
- Reel file: every word on screen comes from that shot's card text
- Voice: 10 of 19 lines say every number and word
- Screenshots: each one shows the menus and buttons the voice names, and every mark sits on its words
- Reel: every card read back exactly, and the length, size and sound are right

