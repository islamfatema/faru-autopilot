# Is anything silently dead?

Checked 2026-10-27. A green workflow run only means the script exited zero. These are the numbers that go quiet instead of loud.

## History

    data written           2026-10-26 (1 days ago)
    last upload            2026-10-26 (1 days ago)
    documentary topics     61 left of 77, 7 a week -> 8.7 weeks
    shorts a day           6
    subscribe test         27 videos assigned
    last 7 days            875 views, 7 likes, 1 comments

## Rise

    data written           2026-10-26 (1 days ago)
    last upload            2026-10-25 (2 days ago)
    documentary topics     54 left of 82, 4 a week -> 13.5 weeks
    shorts a day           2
    subscribe test         7 videos assigned
    last 7 days            633 views, 10 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## FaRu Fact

    data written           2026-10-26 (1 days ago)
    last upload            2026-10-26 (1 days ago)
    documentary topics     48 left of 72, 4 a week -> 12.0 weeks
    shorts a day           6
    subscribe test         17 videos assigned
    last 7 days            2039 views, 9 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## Publishable scripts left, after the gate

    Run from each channel's own machine, because the gate is part of it:

        cd autopilot_<key> && python -c "import main_<key>"

    main_*.py prints the share of its bank the click rule blocks at startup, and demotes it to a ranking signal above 60%.

## Problems

    - Rise took 633 views in a week and not one comment - check the question seeding
    - FaRu Fact took 2039 views in a week and not one comment - check the question seeding

