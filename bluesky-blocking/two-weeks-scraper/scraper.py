from atproto import FirehoseSubscribeReposClient, parse_subscribe_repos_message, CAR, IdResolver, DidInMemoryCache
import json
import time
from datetime import datetime
from collections import OrderedDict
import resource
import threading
import re
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import signal
import sys
from pathlib import Path
import warnings

# Suppress Pydantic warnings from atproto library
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")
warnings.filterwarnings("ignore", message=".*'default' attribute.*Field.*")

def setup_logging(log_level="INFO", log_file="scraper.log"):
    """
    Setup logging configuration with optional rotation.
    
    Logging levels:
    - DEBUG: All logs including httpx/httpcore HTTP requests
    - INFO: Errors/warnings + stats (startup, periodic stats, shutdown)
    - WARNING: Errors/warnings only
    - NONE: No logs
    """
    
    # Handle NONE case to disable logging
    if log_level.upper() == 'NONE':
        logging.basicConfig(level=logging.CRITICAL + 1)
        # Also disable third-party loggers
        logging.getLogger('httpx').setLevel(logging.CRITICAL + 1)
        logging.getLogger('httpcore').setLevel(logging.CRITICAL + 1)
        logging.getLogger('atproto').setLevel(logging.CRITICAL + 1)
        logging.getLogger('atproto_core').setLevel(logging.CRITICAL + 1)
        return logging.getLogger(__name__)

    log_level_obj = getattr(logging, log_level.upper())
    
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level_obj)
    
    # Prevent adding handlers multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Add stream handler to print to console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(log_level_obj)
    logger.addHandler(stream_handler)

    # Add file handler (rotating or simple)
    if log_file:
        file_handler = TimedRotatingFileHandler(
            log_file, when="midnight", interval=1, backupCount=14
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level_obj)
        logger.addHandler(file_handler)
    
    # Configure third-party library loggers based on log level
    # Only show third-party logs if level is DEBUG or INFO
    if log_level.upper() == 'INFO':
        # For INFO, suppress verbose httpx/httpcore logs but keep errors
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('atproto').setLevel(logging.WARNING)
        logging.getLogger('atproto_core').setLevel(logging.WARNING)
    elif log_level.upper() == 'DEBUG':
        # For DEBUG, show everything
        logging.getLogger('httpx').setLevel(logging.DEBUG)
        logging.getLogger('httpcore').setLevel(logging.DEBUG)
        logging.getLogger('atproto').setLevel(logging.DEBUG)
        logging.getLogger('atproto_core').setLevel(logging.DEBUG)
    else:
        # For WARNING, ERROR, CRITICAL - only show those levels
        logging.getLogger('httpx').setLevel(log_level_obj)
        logging.getLogger('httpcore').setLevel(log_level_obj)
        logging.getLogger('atproto').setLevel(log_level_obj)
        logging.getLogger('atproto_core').setLevel(log_level_obj)
        
    return logger

def load_json_file(filename):
    """Safely load JSON file with error handling"""
    if not os.path.exists(filename):
        print(f"File {filename} does not exist")
        return []

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            if os.path.getsize(filename) == 0:
                return []
            return json.load(f)

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from {filename}: {e}")
        return []
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return []

def append_to_jsonl(data, filename=None):
    """Append data to JSONL file - automatically continues from previous runs"""
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"data_{timestamp}.json"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            if isinstance(data, set):
                data = list(data)
            json_line = json.dumps(data, ensure_ascii=False)
            f.write(json_line + '\n')
    except Exception as e:
        print(f"Error appending to JSONL file: {e}")


class Config:
    def __init__(self, config_file=None):
        if config_file is None:
            config_file = os.getenv('CONFIG_FILE', 'config.json')
        self.config_file = config_file
        self.data = self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file {self.config_file} not found")

        with open(self.config_file, 'r') as f:
            return json.load(f)

    def get(self, key, default=None):
        """Get config value using dot notation: 'database.host'"""
        keys = key.split('.')
        value = self.data
        for k in keys:
            value = value.get(k, {})
        return value if value != {} else default

    def __getitem__(self, key):
        return self.get(key)


class ActionClassifier:
    def __init__(self, filename,action_save):
        self.seen_actions = set(load_json_file(filename))
        self.filename = filename
        self.action_save = action_save
        return


    def add_action(self, action):
        if not self.action_save:
            return
        self.seen_actions.add(action)
        return

    def save_new_actions(self):
        if not self.action_save:
            return
        append_to_jsonl(self.seen_actions, self.filename)


class FirehoseScraper:
    def __init__(self, action_classifier, config, verbose=False):
        self.action_classifier = action_classifier
        self.config = config
        self.resolver = IdResolver(cache=DidInMemoryCache())
        # Create ActionScraper with a bounded handle cache to avoid unbounded memory growth
        cache_max = int(self.config.get('resolver.cache_max_size', 10000))
        self.actionScraper = ActionScraper(action_classifier, verbose, cache_max=cache_max)
        self.post_count = 0
        self.running = False
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.last_stats_log = time.time()
        self.stats = {
            'start_time': None,
            'total_processed': 0,
            'errors': 0,
            'reconnects': 0
        }
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Create output directory
        self.output_dir = Path(config.get('output.base_directory', './data'))
        self.output_dir.mkdir(exist_ok=True)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self._stop_collection()
        sys.exit(0)

    def _get_current_output_file(self):
        """Get current output file based on date rotation"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        return self.output_dir / f"{current_date}.jsonl"

    def _firehose_callback(self, message):
        """Callback function for FirehoseSubscribeReposClient"""
        try:
            # Process the message through your ActionScraper
            current_file = self._get_current_output_file()
            self.actionScraper.process_action(message, self.resolver, str(current_file))
            self.post_count += 1
            self.stats['total_processed'] += 1
            
            # Periodic logging and maintenance
            current_time = time.time()
            
            # Log stats periodically
            stats_interval = self.config.get('scraping.log_stats_interval', 300)
            if current_time - self.last_stats_log > stats_interval:
                self._log_stats()
                self.last_stats_log = current_time

        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error in firehose callback: {e}")

    def _log_stats(self):
        """Log current statistics"""
        uptime = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
        rate = self.stats['total_processed'] / uptime if uptime > 0 else 0
        # Include resident set size (RSS) to help detect memory growth
        try:
            rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception:
            rss_kb = 0

        self.logger.info(
            f"Stats: {self.stats['total_processed']} processed, "
            f"{self.stats['errors']} errors, "
            f"{rate:.1f} actions/sec, "
            f"{uptime/3600:.1f}h uptime, "
            f"rss_kb={rss_kb}"
        )

    def start_collection(self, duration_seconds=None, post_limit=None):
        self.start_time = time.time()
        self.stats['start_time'] = self.start_time
        end_time = self.start_time + duration_seconds if duration_seconds else None
        self.running = True
        
        self.logger.info(f"Starting collection for {duration_seconds/86400:.1f} days" if duration_seconds else "Starting indefinite collection")

        def check_limits():
            while self.running:
                current_time = time.time()
                if self.verbose:
                    if end_time:
                        self.logger.debug(f"Time remaining: {(end_time - current_time)/3600:.1f} hours")
                
                if duration_seconds and current_time >= end_time:
                    self.logger.info("Time limit reached.")
                    self._stop_collection()
                    break
                elif post_limit and self.post_count >= post_limit:
                    self.logger.info("Post limit reached.")
                    self._stop_collection()
                    break
                time.sleep(60)  # Check every minute instead of every second

        def run_firehose():
            """Run the firehose with automatic reconnection"""
            max_attempts = self.config.get('firehose.max_reconnect_attempts', 100)
            attempt = 0
            
            while self.running and attempt < max_attempts:
                try:
                    self.client = FirehoseSubscribeReposClient()
                    self.logger.info(f"Connecting to firehose (attempt {attempt + 1})")
                    self.client.start(self._firehose_callback)
                except Exception as e:
                    attempt += 1
                    self.stats['reconnects'] += 1
                    self.logger.error(f"Firehose error (attempt {attempt}): {e}")
                    if attempt < max_attempts and self.running:
                        wait_time = min(300, 30 * attempt)  # Exponential backoff, max 5min
                        self.logger.info(f"Reconnecting in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        self.logger.error("Max reconnect attempts reached")
                        self.running = False

        try:
            # Start limit checking in a separate thread
            limit_thread = threading.Thread(target=check_limits, daemon=True)
            limit_thread.start()
            
            # Run firehose with reconnection logic
            run_firehose()

        except Exception as e:
            self.logger.error(f"Error in collection: {e}")
            self.running = False

        return

    def _stop_collection(self):
        self.running = False
        elapsed = time.time() - self.start_time if self.start_time else 0
        self.logger.info("Collection stopping...")
        self.logger.info(f"Final stats: {self.stats['total_processed']} processed, "
                        f"{self.stats['errors']} errors, "
                        f"{self.stats['reconnects']} reconnects, "
                        f"{elapsed/3600:.1f}h runtime")

        # Save final stats
        try:
            stats_file = self.config.get('monitoring.stats_file', 'scraper_stats.json')
            with open(stats_file, 'w') as f:
                json.dump({
                    **self.stats,
                    'end_time': time.time(),
                    'total_runtime_hours': elapsed/3600
                }, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving stats: {e}")

        self.action_classifier.save_new_actions()
        
        try:
            if hasattr(self, 'client'):
                self.client.stop()
        except Exception as e:
            self.logger.error(f"Error stopping client: {e}")
        
        self.logger.info("Collection stopped")

def classify_type_action(path, action_classifier):
    # Match the pattern: namespace.action/record_id
    match = re.match(r'([a-z]+\.[a-z]+\.[a-z]+)\.([a-z]+)/(.+)', path)
    if not match:
        return
    namespace = match.group(1)  # "app.bsky.feed"
    action = match.group(2)  # "like"
    record_id = match.group(3)  # "3lcaqus3rxq2c"

    action_classifier.add_action(namespace + '.' +action)
    return record_id

class ActionScraper:
    def __init__(self, action_classifier, verbose=False, cache_max=10000):
        self.action_classifier = action_classifier
        self.verbose = verbose
        # Local bounded LRU cache for DID -> handle resolution.
        # We keep this local (instead of relying only on the atproto cache)
        # so we can bound memory usage on long runs.
        self.handle_cache = OrderedDict()
        self.handle_cache_max = int(cache_max or 10000)

    def process_action(self,message, resolver, output_file):
        try:
            commit = parse_subscribe_repos_message(message)

            if self.verbose:
                print("")
                print("")
                print(f"Processing commit: {commit}")

            if not hasattr(commit, 'ops'):
                return

            for op in commit.ops:

                rKey = classify_type_action(op.path, self.action_classifier)

                data_to_save = self._extract_metadata(commit, op, resolver, rKey)

                if self.verbose:
                    print(f"Processing op: {op}")

                new_data = self._process_CAR_data(commit, op, resolver)

                data_to_save.update(new_data)
                self._save_data(data_to_save, output_file)


        except Exception as e:
            print(f"Error processing action: {e}")

    def _extract_metadata (self, commit, op, resolver, rKey):
        author_handle = self._resolve_author_handle(commit.repo, resolver)
        timestamp = commit.time
        action = op.action

        return {
            'author': author_handle,
            'rkey': rKey, # rkey is necessary for the deletes
            'created_at': timestamp,
            'action': action,
        }

    def _process_CAR_data(self, commit, op, resolver):
        ACTION_HANDLERS = {
            'app.bsky.feed.post': '_extract_post_data',
            'app.bsky.feed.like': '_extract_like_data',
            'app.bsky.feed.repost': '_extract_repost_data',
            'app.bsky.graph.follow': '_extract_follow_data',
            'app.bsky.graph.block': '_extract_block_data',
            "app.bsky.feed.threadgate" : "_extract_thread_data",
            "app.bsky.feed.postgate" : "_extract_postgate_data",
            "app.bsky.actor.status" : "_extract_actor_data",
            "app.bsky.actor.profile" : "_extract_profile_data",
            "app.bsky.graph.listitem" : "_extract_listitem_data",
            'app.bsky.graph.listblock' : '_extract_listblock_data',
            'app.bsky.graph.list' : '_extract_list_data',
        }
        """Process a single post operation"""
        try:
            car = CAR.from_bytes(commit.blocks)
            if self.verbose:
                print(f"Processing car: {car}")
                print(f"Processing car.blocks: {car.blocks}")
                print(f"Processing car.blocks.values() : {car.blocks.values()}")
            for record in car.blocks.values():

                if self.verbose:
                    print(f"Processing record: {record}")

                if isinstance(record, dict):
                    type_action = record.get('$type')

                    if type_action:

                        if self.verbose:
                            print(f"Processing type_action: {type_action}")

                        handler_name = ACTION_HANDLERS.get(type_action)

                        if handler_name:

                            handler_method = getattr(self, handler_name)
                            return handler_method(record, commit.repo, op.path, type_action, resolver)

            return {}
        
        except Exception as e:
            print(f"Error processing record: {e}")

    def _resolve_author_handle(self, repo, resolver):
        """Resolve the author handle from the DID"""
        # Defensive: empty or None repo
        if not repo:
            return repo

        # Check local LRU cache first
        try:
            if repo in self.handle_cache:
                # Move to end to mark as recently used
                handle = self.handle_cache.pop(repo)
                self.handle_cache[repo] = handle
                return handle
        except Exception:
            # fall through to resolution
            pass

        try:
            resolved_info = resolver.did.resolve(repo)
            handle = (resolved_info.also_known_as[0].split('at://')[1]
                      if resolved_info.also_known_as else repo)
        except Exception as e:
            if self.verbose:
                print(f"Could not resolve handle for {repo}: {e}")
            handle = repo  # Fallback to DID

        # Store in LRU cache, evict oldest if needed
        try:
            self.handle_cache[repo] = handle
            if len(self.handle_cache) > self.handle_cache_max:
                # popitem(last=False) removes the oldest entry
                self.handle_cache.popitem(last=False)
        except Exception:
            # ignore caching errors to avoid crashing scraper
            pass

        return handle

    def _extract_post_data(self,record, repo, path, typeof_action, resolver):
        try:
            """Extract post data from a record"""
            has_images = self._check_for_images(record)
            reply_to = self._get_reply_to(record)

            reply = record.get('reply','')
            if(reply != ''):
                reply_root = reply.get('root','')
                root_url = reply_root.get('uri', '')
                did_root, event = self.extract_EventAndDidFromURI(root_url)
                did_root = self._resolve_author_handle(did_root, resolver)
                reply_parent = reply.get('parent', '')
                parent_url = reply_parent.get('uri', '')
                did_parent, event = self.extract_EventAndDidFromURI(parent_url)
                did_parent = self._resolve_author_handle(did_parent, resolver)
            else:
                reply_root = ''
                root_url = ''
                did_root = ''
                did_parent = ''

        except Exception as e:
            print(f"Error processing post: {e}")
            has_images=''
            reply_to=''
            did_root=''
            did_parent=''

        return {
            'typeOfAction': typeof_action,
            'text': record.get('text', ''),
            'has_images': has_images,
            'reply_to': reply_to,
            'lang': record.get('langs', ''),
            'reply': {
                'root_did': did_root,
                'parent_did': did_parent
            }

        }

    def _extract_like_data(self, record, repo, path, typeof_action, resolver):
        #DATA SPLITTING
        # 'at://did:plc:7exlcsle4mjfhu3wnhcgizz6/app.bsky.feed.post/3m5yn47qncs2n'
        # Split by '/' to get the main parts
        try:
            subject = record.get('subject', '')
            url=subject.get('uri', '')
            did, event = self.extract_EventAndDidFromURI(url)
            DidUsername = self._resolve_author_handle(did, resolver)
        except Exception as e:
            print(f"Error processing like: {e}")
            DidUsername = ''
            event = ''

        return {
            'typeOfAction': typeof_action,
            'subject': {
                'did_id': DidUsername,
                'collection': event
            }
        }

    def _extract_repost_data(self, record, repo, path, typeof_action, resolver):

        # DATA SPLITTING
        # 'at://did:plc:7exlcsle4mjfhu3wnhcgizz6/app.bsky.feed.post/3m5yn47qncs2n'
        # Split by '/' to get the main parts
        try:
            subject = record.get('subject', '')
            url = subject.get('uri', '')
            did, event = self.extract_EventAndDidFromURI(url)
            DidUsername = self._resolve_author_handle(did, resolver)
        except Exception as e:
            print(f"Error processing repost: {e}")
            DidUsername = ''
            event = ''

        return {
            'typeOfAction': typeof_action,
            'subject': {
                'did_id': DidUsername,
                'collection': event
            }
        }

    def _extract_block_data(self,record, repo, path, typeof_action, resolver):

        try:
            DidUsername = self._resolve_author_handle(record.get('subject'), resolver)
        except Exception as e:
            print(f"Error processing block: {e}")
            DidUsername = ''

        return {
            'typeOfAction': typeof_action,
            'subject': {
                'subject_id': DidUsername
            }
        }

    def _extract_follow_data(self,record, repo, path, typeof_action, resolver):
        try:
            DidUsername = self._resolve_author_handle(record.get('subject'), resolver)
        except Exception as e:
            print(f"Error processing follow: {e}")
            DidUsername = ''

        return {
            'typeOfAction': typeof_action,
            'subject': {
                'subject_id': DidUsername
            }
        }

    def _extract_actor_data(self,record, repo, path, typeof_action, resolver):

        try:
            embed = record.get('embed','')
            embed_type = embed.get('$type','')
            external= embed.get('external','')
            uri = external.get('uri','')
            title = external.get('title','')
            description = external.get('description','')
            status = record.get('status','')
            duration = record.get('durationMinutes','')
        except Exception as e:
            print(f"Error processing actor: {e}")
            embed_type = ''
            uri = ''
            title = ''
            description = ''
            status = ''
            duration = ''

        return {
            'typeOfAction': typeof_action,
            'embedType': embed_type,
            'uri': uri,
            'title': title,
            'description': description,
            'status': status,
            'duration': duration
        }

    def _extract_profile_data(self,record, repo, path, typeof_action, resolver):
        return {
            'typeOfAction': typeof_action,
            'description': record.get('description',''),
            'displayName': record.get('displayName','')
        }

    def _extract_listitem_data(self,record, repo, path, typeof_action, resolver):

        try:
            list = record.get('list', '')
            list_did, list_event = self.extract_EventAndDidFromURI(list)
            list_UsernameDid = self._resolve_author_handle(list_did, resolver)
            subject_id = self._resolve_author_handle(list_did, resolver)
        except Exception as e:
            print(f"Error processing listitem: {e}")
            list_UsernameDid = ''
            subject_id = ''
            list_event = ''

        return {
            'typeOfAction': typeof_action,
            'subject_id': subject_id,
            'list': {
                'did_id': list_UsernameDid,
                'collection': list_event
            }
        }

    def _extract_postgate_data(self,record, repo, path, typeof_action, resolver):

        try:
            post = record.get('post', '')
            post_did, post_event = self.extract_EventAndDidFromURI(post)
            post_Username = self._resolve_author_handle(post_did, resolver)
            embeddingRules = record.get('embeddingRules', [])
            detachedEmbeddingUris = record.get('detachedEmbeddingUris', [])
        except Exception as e:
            print(f"Error processing postgate: {e}")
            post_Username = ''
            embeddingRules = ''
            detachedEmbeddingUris = ''
            post_event = ''

        return {
            'typeOfAction': typeof_action,
            'post': {
                'did_id': post_Username,
                'collection': post_event
            },
            'embeddingRules': embeddingRules,
            'detachedEmbeddingUris': detachedEmbeddingUris
        }

    def _extract_thread_data(self,record, repo, path, typeof_action, resolver):

        try:
            post = record.get('post', '')
            post_did, post_event = self.extract_EventAndDidFromURI(post)
            post_Username = self._resolve_author_handle(post_did, resolver)
            allow =record.get('allow', [])
            allow_type= allow.get('$type','')
            allow_hiddenReplies = allow.get('hiddenReplies', [])
        except Exception as e:
            print(f"Error processing thread: {e}")
            allow_type = ''
            allow_hiddenReplies = ''
            post_event = ''
            post_Username = ''

        return {
            'typeOfAction': typeof_action,
            'post': {
                'did_id': post_Username,
                'collection': post_event
            },
            'allow': {
                'type': allow_type,
                'hiddenReplies': allow_hiddenReplies
            }
        }

    def _extract_listblock_data(self,record, repo, path, typeof_action, resolver):

        try:
            subject = record.get('subject', '')
            url = subject.get('uri', '')
            did, event = self.extract_EventAndDidFromURI(url)
        except Exception as e:
            print(f"Error processing listblock: {e}")
            did = ''
            event = ''

        return {
            'typeOfAction': typeof_action,
            'subject': {
                'did_id': did,
                'collection': event
            }
        }

    def _extract_list_data(self,record, repo, path, typeof_action, resolver):

        # Some records for lists can unexpectedly be lists (or other types)
        # instead of a dict. Be defensive and handle those cases so we
        # don't raise "'list' object has no attribute 'get'".
        try:
            if isinstance(record, dict):
                purpose = record.get('purpose', '')
                name = record.get('name', '')
                description = record.get('description', '')

            elif isinstance(record, list):
                # If it's a list, try to find the first dict-like entry
                first = next((r for r in record if isinstance(r, dict)), None)
                if first:
                    purpose = first.get('purpose', '')
                    name = first.get('name', '')
                    description = first.get('description', '')
                else:
                    purpose = name = description = ''

            else:
                # Unknown shape, return empty values
                purpose = name = description = ''

        except Exception as e:
            # Preserve existing behaviour of verbose printing for debugging
            if getattr(self, 'verbose', False):
                print(f"Error processing list: {e}")
            purpose = name = description = ''

        return {
            'typeOfAction': typeof_action,
            'purpose': purpose,
            'name': name,
            'description': description
        }


    def _check_for_images(self,record):
        """Check if the post has images"""
        embed = record.get('embed', {})
        return (
                embed.get('$type') == 'app.bsky.embed.images' or
                (embed.get('$type') == 'app.bsky.embed.external' and 'thumb' in embed)
        )

    def _get_reply_to(self,record):
        """Get the URI of the post being replied to"""
        reply_ref = record.get('reply', {})
        return reply_ref.get('parent', {}).get('uri')

    def _save_data(self, post_data, output_file):
        """Save post data to the output file"""
        with open(output_file, 'a') as f:
            json.dump(post_data, f)
            f.write('\n')

    def extract_EventAndDidFromURI(self, url):
        """Extract event and did from the URI"""
        parts = url.split('/')
        # parts: ['at:', '', 'did:plc:7exlcsle4mjfhu3wnhcgizz6', 'app.bsky.feed.post', '3m5yn47qncs2n']

        did_part = parts[2]  # 'did:plc:7exlcsle4mjfhu3wnhcgizz6'
        event = parts[3]  # 'app.bsky.feed.post'

        # Extract just the DID portion (remove 'did:plc:')
        did = did_part.split(':')[-1]  # '7exlcsle4mjfhu3wnhcgizz6'

        return did, event


def main():
    try:
        config = Config()
        
        action_filename = config.get("actions.filename")
        action_save = config.get("actions.save")

        verbose = config.get("firehose.verbose")
        scraping_duration = config.get("scraping.time_limit")
        scraping_limit = config.get("scraping.action_limit")

        log_level = config.get("logging.level", "INFO")

        logger = setup_logging(log_level=log_level)
        logger.info("Starting Firehose Scraper")

        logger.info(f"Configuration loaded: {scraping_duration/86400:.1f} days duration")

        action_classifier = ActionClassifier(action_filename, action_save)
        firehose_scraper = FirehoseScraper(action_classifier, config, verbose)

        firehose_scraper.start_collection(duration_seconds=scraping_duration, post_limit=scraping_limit)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

