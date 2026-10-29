# Is anything silently dead?

Checked 2026-10-29. A green workflow run only means the script exited zero. These are the numbers that go quiet instead of loud.

## History

    data written           2026-10-28 (1 days ago)
    last upload            2026-10-28 (1 days ago)
    documentary topics     60 left of 78, 7 a week -> 8.6 weeks
    shorts a day           6
    subscribe test         39 videos assigned
    last 7 days            1209 views, 11 likes, 1 comments

## Rise

    data written           2026-10-28 (1 days ago)
    last upload            2026-10-27 (2 days ago)
    documentary topics     57 left of 86, 4 a week -> 14.2 weeks
    shorts a day           2
    subscribe test         11 videos assigned
    last 7 days            729 views, 11 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## FaRu Fact

    data written           2026-10-28 (1 days ago)
    last upload            2026-10-28 (1 days ago)
    documentary topics     49 left of 74, 4 a week -> 12.2 weeks
    shorts a day           6
    subscribe test         29 videos assigned
    last 7 days            1847 views, 11 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## Publishable scripts left, after the gate

    Run from each channel's own machine, because the gate is part of it:

        cd autopilot_<key> && python -c "import main_<key>"

    main_*.py prints the share of its bank the click rule blocks at startup, and demotes it to a ranking signal above 60%.

## Problems

    - Rise took 729 views in a week and not one comment - check the question seeding
    - FaRu Fact took 1847 views in a week and not one comment - check the question seeding

