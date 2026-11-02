# Is anything silently dead?

Checked 2026-11-02. A green workflow run only means the script exited zero. These are the numbers that go quiet instead of loud.

## History

    data written           2026-11-01 (1 days ago)
    last upload            2026-11-01 (1 days ago)
    documentary topics     58 left of 80, 7 a week -> 8.3 weeks
    shorts a day           5
    subscribe test         62 videos assigned
    last 7 days            1753 views, 9 likes, 4 comments

## Rise

    data written           2026-11-01 (1 days ago)
    last upload            2026-10-31 (2 days ago)
    documentary topics     59 left of 90, 4 a week -> 14.8 weeks
    shorts a day           5
    subscribe test         21 videos assigned
    last 7 days            1126 views, 23 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## FaRu Fact

    data written           2026-11-01 (1 days ago)
    last upload            2026-11-01 (1 days ago)
    documentary topics     51 left of 78, 4 a week -> 12.8 weeks
    shorts a day           4
    subscribe test         52 videos assigned
    last 7 days            583 views, 3 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## Publishable scripts left, after the gate

    Run from each channel's own machine, because the gate is part of it:

        cd autopilot_<key> && python -c "import main_<key>"

    main_*.py prints the share of its bank the click rule blocks at startup, and demotes it to a ranking signal above 60%.

## Problems

    - Rise took 1126 views in a week and not one comment - check the question seeding
    - FaRu Fact took 583 views in a week and not one comment - check the question seeding

