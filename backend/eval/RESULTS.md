# Evaluation results

Model `all-MiniLM-L6-v2`, relevance floor 0.25, k = 5. Labels were drafted from the catalogue text (see `queries.json`); treat them as a first pass to be reviewed.

**P@5** is the textbook definition (relevant items in the top 5, divided by 5), so a query with only one relevant product can score at most 0.20. **Recall@5**, **MRR** and **Hit@1** are shown beside it for that reason.

## Summary

| Query class | n | Method | P@5 | Recall@5 | MRR | Hit@1 |
|---|---|---|---|---|---|---|
| exact | 10 | keyword | 0.24 | 1.00 | 1.00 | 1.00 |
|  |  | semantic | 0.24 | 1.00 | 1.00 | 1.00 |
|  |  | hybrid | 0.24 | 1.00 | 1.00 | 1.00 |
| paraphrase | 10 | keyword | 0.00 | 0.00 | 0.00 | 0.00 |
|  |  | semantic | 0.24 | 1.00 | 0.95 | 0.90 |
|  |  | hybrid | 0.24 | 1.00 | 0.95 | 0.90 |
| vague | 10 | keyword | 0.02 | 0.05 | 0.10 | 0.10 |
|  |  | semantic | 0.32 | 0.73 | 0.73 | 0.60 |
|  |  | hybrid | 0.32 | 0.73 | 0.73 | 0.60 |
| overall | 30 | keyword | 0.09 | 0.35 | 0.37 | 0.37 |
|  |  | semantic | 0.27 | 0.91 | 0.89 | 0.83 |
|  |  | hybrid | 0.27 | 0.91 | 0.89 | 0.83 |

## Queries with no right answer

Nothing in the catalogue matches these. The correct behaviour is an empty result.

| Method | Correctly empty | Results returned per query |
|---|---|---|
| keyword | 3 / 3 | [0, 0, 0] |
| semantic | 3 / 3 | [0, 0, 0] |
| hybrid | 3 / 3 | [0, 0, 0] |

## Per query

| ID | Query | Relevant | Keyword MRR | Semantic MRR | Hybrid MRR |
|---|---|---|---|---|---|
| E01 | running shoes | 1 | 1.00 | 1.00 | 1.00 |
| E02 | yoga mat | 1 | 1.00 | 1.00 | 1.00 |
| E03 | mechanical keyboard | 1 | 1.00 | 1.00 | 1.00 |
| E04 | robot vacuum | 1 | 1.00 | 1.00 | 1.00 |
| E05 | standing desk | 2 | 1.00 | 1.00 | 1.00 |
| E06 | ergonomic mouse | 1 | 1.00 | 1.00 | 1.00 |
| E07 | gaming laptop | 1 | 1.00 | 1.00 | 1.00 |
| E08 | hiking boots | 1 | 1.00 | 1.00 | 1.00 |
| E09 | TrailMaster | 2 | 1.00 | 1.00 | 1.00 |
| E10 | Galaxy Nova 14 Pro | 1 | 1.00 | 1.00 | 1.00 |
| P01 | warm winter jacket for men | 1 | 0.00 | 1.00 | 1.00 |
| P02 | footwear for plantar fasciitis | 1 | 0.00 | 1.00 | 1.00 |
| P03 | headphones that cancel outside sound | 1 | 0.00 | 1.00 | 1.00 |
| P04 | cell phone with a great camera but cheap | 1 | 0.00 | 1.00 | 1.00 |
| P05 | laptop for a student on a tight budget | 2 | 0.00 | 1.00 | 1.00 |
| P06 | chair that supports my lower back | 1 | 0.00 | 1.00 | 1.00 |
| P07 | pot for slow cooked stews | 2 | 0.00 | 1.00 | 1.00 |
| P08 | wireless earphones for the gym | 1 | 0.00 | 1.00 | 1.00 |
| P09 | gadget to track my workouts and heart rate | 1 | 0.00 | 1.00 | 1.00 |
| P10 | something to keep my coffee hot | 1 | 0.00 | 0.50 | 0.50 |
| V01 | something to help me sleep better | 2 | 1.00 | 1.00 | 1.00 |
| V02 | gift for someone who loves cooking | 4 | 0.00 | 1.00 | 1.00 |
| V03 | gear for a camping trip | 5 | 0.00 | 0.50 | 0.50 |
| V04 | relieve wrist and back pain while working at a desk | 4 | 0.00 | 1.00 | 1.00 |
| V05 | keep my home air clean for allergies | 1 | 0.00 | 1.00 | 1.00 |
| V06 | get fit at home without a gym | 3 | 0.00 | 0.33 | 0.33 |
| V07 | teach my kid about programming | 1 | 0.00 | 0.50 | 0.50 |
| V08 | what to wear to a job interview | 2 | 0.00 | 1.00 | 1.00 |
| V09 | protect my skin from the sun | 1 | 0.00 | 1.00 | 1.00 |
| V10 | make music at home | 1 | 0.00 | 0.00 | 0.00 |

## Where semantic search missed

**P10 - "something to keep my coffee hot"** (wanted: Insulated Water Bottle 32oz)

1. Programmable Coffee Maker 12-Cup
2. Insulated Water Bottle 32oz  <- relevant
3. Insulated Men's Parka

**V03 - "gear for a camping trip"** (wanted: Waterproof Hiking Boots, Waterproof Hiking Jacket, Portable Power Station 500W, Compact Binoculars 10x42, Rugged Outdoor Phone X5)

1. Travel Backpack 40L Carry-On
2. Waterproof Hiking Jacket  <- relevant
3. Insulated Men's Parka
4. Down Puffer Vest
5. Tailored Blazer Jacket

**V06 - "get fit at home without a gym"** (wanted: Adjustable Dumbbell Set 5-52 lbs, Resistance Bands Set of 5, Yoga Mat Premium 6mm)

1. Fitness Tracker Watch
2. High-Waist Yoga Leggings
3. Resistance Bands Set of 5  <- relevant

**V07 - "teach my kid about programming"** (wanted: STEM Building Robot Kit)

1. Kids Bicycle 20-inch
2. STEM Building Robot Kit  <- relevant

**V10 - "make music at home"** (wanted: Studio Monitor Speakers Pair)

1. Vintage Vinyl Turntable

