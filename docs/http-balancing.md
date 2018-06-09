## HTTP balancing

HTTP request balancing and retries is done using virtual hosts, similar to upstreams in nginx.

Each virtual host is added or modified using `register_upstream` method of HttpClientFactory instance:
* `name` - any unique string used to identify virtual host
* `upstream_config` - dict with configuration parameters:
    * `max_tries` - maximum number of tries to perform request
    * `max_fails` - maximum concurrent errors for server to be considered dead
    * `fail_timeout_sec` - timeout before restoring a dead server
    * `connect_timeout_sec` - default connect timeout for requests to this host
    * `request_timeout_sec` - default request timeout for requests to this host
    * `max_timeout_tries` - request timeout multiplier
    * `slow_start_interval_sec` - if set, new or restored server won't be used until rand([0, slow_start_interval_sec]) seconds has passed
    * `slow_start_requests` - if set, new or restored server will not be used for more than one concurrent request until this number of requests will be finished
    * `retry_policy` - comma-separated string specifying when request is eligible for retry, for example: "timeout,http_503,non_idempotent_503" 
* `servers` - list of Server objects with:
    * `server` - ip address and port of the server
    * `weigth` - controls how many requests should be send to this server
    * `rack` - group servers by rack or blade system. Client will try to make a retry request to a different rack
    * `dc` - unless specifically allowed, servers from datacenter other than that of the current application will be ignored

Virtual host could be added, updated or deleted at any time.
To make configuration of virtual hosts easier, `update_upstream` function accepts string representation of configuration:

`max_tries=10 fail_timeout_sec=1 max_fails=30 request_timeout_sec=0.2 connect_timeout_sec=1 max_timeout_tries=2 | server=172.17.0.1:1111 | server=172.17.0.1:2222`
