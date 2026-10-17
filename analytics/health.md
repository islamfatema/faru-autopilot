# Is anything silently dead?

Checked 2026-10-17. A green workflow run only means the script exited zero. These are the numbers that go quiet instead of loud.

## History

    data written           2026-10-13 (4 days ago)   <-- PROBLEM
    last upload            2026-10-13 (4 days ago)   (but the file is 4 days old, so this may just be the stale data above)
    documentary topics     46 left of 57, 7 a week -> 6.6 weeks
    shorts a day           8
    last 7 days            2086 views, 48 likes, 1 comments

## Rise

    data written           2026-10-13 (4 days ago)   <-- PROBLEM
    last upload            2026-10-13 (4 days ago)   (but the file is 4 days old, so this may just be the stale data above)
    documentary topics     40 left of 62, 4 a week -> 10.0 weeks
    shorts a day           3
    last 7 days            73 views, 0 likes, 0 comments

## FaRu Fact

    data written           2026-10-17 (0 days ago)
    last upload            2026-10-17 (0 days ago)
    documentary topics     30 left of 51, 4 a week -> 7.5 weeks
    shorts a day           2
    last 7 days            753 views, 5 likes, 0 comments
                           <-- PROBLEM: views but no comments at all

## Publishable scripts left, after the gate

    Run from each channel's own machine, because the gate is part of it:

        cd autopilot_<key> && python -c "import main_<key>"

    main_*.py prints the share of its bank the click rule blocks at startup, and demotes it to a ranking signal above 60%.

## Problems

    - History's analytics have not reached the repo for 4 days - every number below it is that old
    - Rise's analytics have not reached the repo for 4 days - every number below it is that old
    - FaRu Fact took 753 views in a week and not one comment - check the question seeding

