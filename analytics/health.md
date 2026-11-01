# Is anything silently dead?

Checked 2026-11-01. A green workflow run only means the script exited zero. These are the numbers that go quiet instead of loud.

## History

    data written           2026-11-01 (0 days ago)
    last upload            2026-11-01 (0 days ago)
    documentary topics     58 left of 79, 7 a week -> 8.3 weeks
    shorts a day           5
    subscribe test         57 videos assigned
    last 7 days            2361 views, 14 likes, 5 comments

## Rise

    data written           2026-11-01 (0 days ago)
    last upload            2026-10-31 (1 days ago)
    documentary topics     60 left of 90, 4 a week -> 15.0 weeks
    shorts a day           5
    subscribe test         17 videos assigned
    last 7 days            1228 views, 24 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## FaRu Fact

    data written           2026-11-01 (0 days ago)
    last upload            2026-11-01 (0 days ago)
    documentary topics     52 left of 78, 4 a week -> 13.0 weeks
    shorts a day           4
    subscribe test         47 videos assigned
    last 7 days            639 views, 3 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## Publishable scripts left, after the gate

    Run from each channel's own machine, because the gate is part of it:

        cd autopilot_<key> && python -c "import main_<key>"

    main_*.py prints the share of its bank the click rule blocks at startup, and demotes it to a ranking signal above 60%.

## Problems

    - Rise took 1228 views in a week and not one comment - check the question seeding
    - FaRu Fact took 639 views in a week and not one comment - check the question seeding

