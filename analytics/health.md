# Is anything silently dead?

Checked 2026-10-28. A green workflow run only means the script exited zero. These are the numbers that go quiet instead of loud.

## History

    data written           2026-10-27 (1 days ago)
    last upload            2026-10-27 (1 days ago)
    documentary topics     61 left of 78, 7 a week -> 8.7 weeks
    shorts a day           6
    subscribe test         33 videos assigned
    last 7 days            952 views, 9 likes, 1 comments

## Rise

    data written           2026-10-27 (1 days ago)
    last upload            2026-10-26 (2 days ago)
    documentary topics     55 left of 83, 4 a week -> 13.8 weeks
    shorts a day           2
    subscribe test         9 videos assigned
    last 7 days            676 views, 11 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## FaRu Fact

    data written           2026-10-27 (1 days ago)
    last upload            2026-10-27 (1 days ago)
    documentary topics     49 left of 73, 4 a week -> 12.2 weeks
    shorts a day           6
    subscribe test         23 videos assigned
    last 7 days            2098 views, 12 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## Publishable scripts left, after the gate

    Run from each channel's own machine, because the gate is part of it:

        cd autopilot_<key> && python -c "import main_<key>"

    main_*.py prints the share of its bank the click rule blocks at startup, and demotes it to a ranking signal above 60%.

## Problems

    - Rise took 676 views in a week and not one comment - check the question seeding
    - FaRu Fact took 2098 views in a week and not one comment - check the question seeding

