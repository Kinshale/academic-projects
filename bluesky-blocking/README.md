# Overview
Information space dynamics in social networks. 

+ Project goals and overview: https://polimi365-my.sharepoint.com/:p:/g/personal/11150791_polimi_it/EbzjokOG_ElLpHDYaLav_bUB2m9Uaw8RX0LsbQ5cQhjBTA?e=yQ0n2S 
+ Deep Learning + LTSM layers

# Data Sources 

## ATProto Firehose
Basically Bluesky relies on a decentralized protocol, and it broadcast in real-time a stream of all network events. 
No rate limits but needs bandwidth/storage and filtering.

```python
from atproto import Firehose
```

## Pre-collected datasets

**URL**: https://bsky.leobalduf.com/datasets.html  
**Format**: Parquet files  
**Content**: 1M+ posts, social graphs, engagements  
**Schema**: `data/database_schema.json`

**URL**: Professors shared dumps (?). 

**URL** 

## Offiacial  API
Free access with rate limits (~3k requests/hour authenticated). 
Authentication: Bluesky handle + app password. 