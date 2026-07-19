"""
Tag Detection Patterns - Centralized configuration for all tracking tools
"""

# Evidence confidence levels
CONFIDENCE_HIGH = 'high'      # network request, response header, meta generator, specific asset path
CONFIDENCE_MEDIUM = 'medium'  # specific JS API pattern, script src URL in HTML
CONFIDENCE_LOW = 'low'        # generic/loose regex match

TAG_PATTERNS = {
    # Google Products
    'google_tag_manager': {
        'patterns': [r'GTM-[A-Z0-9]{4,}'],
        'urls': ['googletagmanager.com/gtm.js', 'googletagmanager.com/ns.html'],
        'owned_domains': ['googletagmanager.com', 'google-analytics.com', 'googleapis.com'],
        'category': 'Tag Management'
    },
    'google_analytics_4': {
        'patterns': [r'G-[A-Z0-9]{10,}'],
        'urls': ['googletagmanager.com/gtag/js', 'google-analytics.com/g/collect'],
        'owned_domains': ['google-analytics.com', 'googletagmanager.com', 'analytics.google.com'],
        'category': 'Analytics'
    },
    'universal_analytics': {
        'patterns': [r'UA-\d+-\d+'],
        'urls': ['google-analytics.com/analytics.js', 'google-analytics.com/ga.js'],
        'category': 'Analytics'
    },
    'google_ads': {
        'patterns': [r'AW-\d+'],
        'urls': ['googleadservices.com/pagead/conversion', 'cm.g.doubleclick.net', 'pagead2.googlesyndication.com'],
        'owned_domains': ['googleadservices.com', 'doubleclick.net', 'googlesyndication.com', 'googleads.g.doubleclick.net'],
        'category': 'Advertising'
    },
    'google_optimize': {
        'patterns': [r'GTM-[A-Z0-9]{4,}'],
        'urls': ['www.googleoptimize.com/optimize.js'],
        'category': 'A/B Testing'
    },
    
    # Meta/Facebook Products
    'facebook_pixel': {
        'patterns': [r'fbq\([\'"]init[\'"]\s*,\s*[\'"](\d+)[\'"]'],
        'urls': ['connect.facebook.net/en_US/fbevents.js', 'facebook.com/tr'],
        'owned_domains': ['facebook.com', 'facebook.net', 'fbcdn.net'],
        'category': 'Advertising'
    },
    'facebook_capi': {
        'patterns': [r'facebook\.com/tr'],
        'urls': ['graph.facebook.com'],
        'category': 'Server-Side Tracking'
    },
    
    # LinkedIn
    'linkedin_insight': {
        'patterns': [r'_linkedin_partner_id\s*=\s*[\'"](\d+)[\'"]'],
        'urls': ['snap.licdn.com/li.lms-analytics', 'px.ads.linkedin.com', 'platform.linkedin.com'],
        'owned_domains': ['linkedin.com', 'licdn.com'],
        'category': 'Advertising'
    },
    
    # TikTok
    'tiktok_pixel': {
        'patterns': [r'ttq\.load\([\'"]([A-Z0-9]+)[\'"]', r'tiktok_pixel_code[\'"]?\s*:\s*[\'"]([A-Z0-9]+)[\'"]'],
        'urls': ['analytics.tiktok.com/i18n/pixel/events.js'],
        'owned_domains': ['tiktok.com', 'tiktokcdn.com'],
        'category': 'Advertising'
    },
    
    # Twitter/X
    'twitter_pixel': {
        'patterns': [r'twq\([\'"]init[\'"]'],
        'urls': ['static.ads-twitter.com/uwt.js'],
        'owned_domains': ['twitter.com', 'ads-twitter.com', 'twimg.com'],
        'category': 'Advertising'
    },
    
    # Snapchat
    'snapchat_pixel': {
        'patterns': [r'snaptr\([\'"]init[\'"]'],
        'urls': ['sc-static.net/scevent.min.js'],
        'category': 'Advertising'
    },
    
    # Pinterest
    'pinterest_tag': {
        'patterns': [r'pintrk\([\'"]load[\'"]'],
        'urls': ['s.pinimg.com/ct/core.js'],
        'category': 'Advertising'
    },
    
    # Reddit
    'reddit_pixel': {
        'patterns': [r'rdt\([\'"]init[\'"]'],
        'urls': ['www.redditstatic.com/ads/pixel.js'],
        'category': 'Advertising'
    },
    
    # Adobe Products
    'adobe_analytics': {
        'patterns': [r's_account\s*=', r'var s=s_gi\('],
        'urls': ['omtrdc.net', 'adobedtm.com'],
        'owned_domains': ['omtrdc.net', 'adobedtm.com', 'demdex.net'],
        'category': 'Analytics'
    },
    'adobe_launch': {
        'patterns': [r'//assets\.adobedtm\.com/'],
        'urls': ['assets.adobedtm.com/launch'],
        'category': 'Tag Management'
    },
    'adobe_target': {
        'patterns': [r'adobe\.target'],
        'urls': ['tt.omtrdc.net'],
        'category': 'A/B Testing'
    },
    
    # Other Tag Managers
    'tealium': {
        'patterns': [r'utag\.js'],
        'urls': ['tags.tiqcdn.com'],
        'category': 'Tag Management'
    },
    'segment': {
        'patterns': [r'analytics\.load\([\'"]([a-zA-Z0-9]+)[\'"]'],
        'urls': ['cdn.segment.com/analytics.js'],
        'owned_domains': ['segment.com', 'segment.io'],
        'category': 'Customer Data Platform'
    },
    
    # Analytics Platforms
    'matomo': {
        'patterns': [r'_paq\.push', r'Matomo\.getTracker'],
        'urls': ['matomo.js', 'piwik.js'],
        'category': 'Analytics'
    },
    'mixpanel': {
        'patterns': [r'mixpanel\.init\([\'"]([a-zA-Z0-9]+)[\'"]'],
        'urls': ['cdn.mxpnl.com/libs/mixpanel'],
        'category': 'Analytics'
    },
    'heap': {
        'patterns': [r'heap\.load\([\'"](\d+)[\'"]'],
        'urls': ['cdn.heapanalytics.com'],
        'category': 'Analytics'
    },
    'amplitude': {
        'patterns': [r'amplitude\.getInstance\(\)\.init\([\'"]([a-zA-Z0-9]+)[\'"]'],
        'urls': ['cdn.amplitude.com'],
        'category': 'Analytics'
    },
    'kissmetrics': {
        'patterns': [r'_kmq\.push'],
        'urls': ['i.kissmetrics.com'],
        'category': 'Analytics'
    },
    'clicky': {
        'patterns': [r'clicky_site_ids\.push\((\d+)\)'],
        'urls': ['static.getclicky.com'],
        'category': 'Analytics'
    },
    
    # Heatmap & Session Recording
    'hotjar': {
        'patterns': [r'hjid:\s*(\d+)', r'hj\([\'"](hjid|identify)[\'"]'],
        'urls': ['static.hotjar.com'],
        'owned_domains': ['hotjar.com', 'hotjar.io'],
        'category': 'Heatmaps'
    },
    'crazy_egg': {
        'patterns': [r'crazyegg'],
        'urls': ['script.crazyegg.com'],
        'category': 'Heatmaps'
    },
    'mouseflow': {
        'patterns': [r'_mfq\.push'],
        'urls': ['cdn.mouseflow.com'],
        'category': 'Heatmaps'
    },
    'fullstory': {
        'patterns': [r'FS\.identify', r'window\[[\'"]\s*_fs_'],
        'urls': ['fullstory.com/s/fs.js'],
        'category': 'Session Recording'
    },
    'lucky_orange': {
        'patterns': [r'_loq\.push', r'LOQ_'],
        'urls': ['d10lpsik1i8c69.cloudfront.net'],
        'category': 'Heatmaps'
    },
    'clarity': {
        'patterns': [r'clarity\([\'"]set[\'"]'],
        'urls': ['clarity.ms'],
        'owned_domains': ['clarity.ms'],
        'category': 'Heatmaps'
    },
    
    # A/B Testing
    'optimizely': {
        'patterns': [r'optimizely'],
        'urls': ['cdn.optimizely.com'],
        'category': 'A/B Testing'
    },
    'vwo': {
        'patterns': [r'_vwo_'],
        'urls': ['dev.visualwebsiteoptimizer.com'],
        'category': 'A/B Testing'
    },
    'ab_tasty': {
        'patterns': [r'ABTasty'],
        'urls': ['try.abtasty.com'],
        'category': 'A/B Testing'
    },
    
    # Consent Management
    'onetrust': {
        'patterns': [r'OneTrust', r'optanon'],
        'urls': ['cdn.cookielaw.org'],
        'category': 'Consent Management'
    },
    'cookiebot': {
        'patterns': [r'Cookiebot'],
        'urls': ['consent.cookiebot.com'],
        'category': 'Consent Management'
    },
    'trustarc': {
        'patterns': [r'truste', r'TrustArc'],
        'urls': ['consent.trustarc.com'],
        'category': 'Consent Management'
    },
    'quantcast': {
        'patterns': [r'quantserve\.com', r'__qca'],
        'urls': ['quantcast.mgr.consensu.org'],
        'owned_domains': ['quantserve.com', 'quantcount.com'],
        'category': 'Consent Management'
    },
    
    # E-commerce Tracking
    'shopify_analytics': {
        'patterns': [r'Shopify\.analytics'],
        'urls': ['cdn.shopify.com/s/javascripts/tricorder'],
        'category': 'E-commerce'
    },
    'shopify_web_pixels': {
        'patterns': [r'web-pixels-manager', r'Shopify\.analytics\.publish'],
        'urls': ['cdn.shopify.com/shopifycloud/web-pixels-manager'],
        'category': 'E-commerce'
    },
    'criteo': {
        'patterns': [r'criteo'],
        'urls': ['static.criteo.net'],
        'category': 'Retargeting'
    },
    'attentive': {
        'patterns': [r'attentive\.com', r'__attentive_domain'],
        'urls': ['cdn.attn.tv', 'events.attentivemobile.com'],
        'category': 'Marketing Automation'
    },
    'yotpo': {
        'patterns': [r'yotpo\.com', r'staticw2\.yotpo\.com', r'data-yotpo-product-id'],
        'urls': ['staticw2.yotpo.com', 'api.yotpo.com'],
        'category': 'E-commerce'
    },
    'nosto': {
        'patterns': [r'nosto', r'nostojs'],
        'urls': ['connect.nosto.com', 'cdn.nosto.com'],
        'category': 'E-commerce'
    },
    'smile_io': {
        'patterns': [r'smile\.io', r'sweettooth'],
        'urls': ['cdn.smile.io', 'js.smile.io'],
        'category': 'E-commerce'
    },
    'rebuy': {
        'patterns': [r'rebuy\.com', r'rebuy-widget'],
        'urls': ['rebuyengine.com', 'cdn.rebuyengine.com'],
        'category': 'E-commerce'
    },
    'privy': {
        'patterns': [r'privy\.com', r'widget\.privy\.com'],
        'urls': ['widget.privy.com', 'dashboard.privy.com'],
        'category': 'Marketing Automation'
    },
    'gorgias': {
        'patterns': [r'gorgias-chat-widget', r'gorgiaschat'],
        'urls': ['config.gorgias.chat', 'cdn.gorgias.chat'],
        'category': 'Customer Support'
    },
    'aftership': {
        'patterns': [r'aftership', r'automizely-tracking'],
        'urls': ['cdn.aftership.com', 'butik.aftership.com'],
        'category': 'E-commerce'
    },
    'recharge': {
        'patterns': [r'rechargepayments\.com', r'rechargecdn\.com'],
        'urls': ['static.rechargecdn.com', 'checkout.rechargeapps.com'],
        'category': 'E-commerce'
    },
    'bold_commerce': {
        'patterns': [r'boldcommerce\.com', r'boldapps\.net'],
        'urls': ['cdn.boldcommerce.com', 'apps.boldapps.net'],
        'category': 'E-commerce'
    },

    # Marketing Automation
    'hubspot': {
        'patterns': [r'_hsq\.push', r'portalId:\s*(\d+)'],
        'urls': ['js.hs-scripts.com', 'js.hubspot.com'],
        'owned_domains': ['hubspot.com', 'hs-scripts.com', 'hs-analytics.net', 'hsforms.com', 'hsforms.net', 'hscollectedforms.net', 'hsadspixel.net', 'hs-banner.com', 'hsappstatic.net', 'hubspotusercontent-na1.net', 'usemessages.com', 'hscollectedforms.net', 'hubspotvideo.com'],
        'category': 'Marketing Automation'
    },
    'marketo': {
        'patterns': [r'Munchkin\.init\([\'"]([0-9]+-[A-Z0-9-]+)[\'"]'],
        'urls': ['munchkin.marketo.net'],
        'category': 'Marketing Automation'
    },
    'pardot': {
        'patterns': [r'piTracker', r'pardot'],
        'urls': ['pi.pardot.com', 'go.pardot.com'],
        'category': 'Marketing Automation'
    },
    'salesforce_marketing_cloud': {
        'patterns': [r'_etmc\.push', r'exacttarget'],
        'urls': ['cdn.evgnet.com', 'click.exacttarget.com', 'mc.s[0-9]+.exacttarget.com'],
        'category': 'Marketing Automation'
    },
    'dynamics_365_marketing': {
        'patterns': [r'msdynmkt', r'd365mkttracking', r'MsCrmMkt'],
        'urls': ['trackcmp.net/visit'],
        'category': 'Marketing Automation'
    },
    'eloqua': {
        'patterns': [r'elqTrackId', r'_elqQ\.push', r'elq\.eloqua\.com'],
        'urls': ['t.eloqua.com', 's[0-9]+.t.eloqua.com'],
        'category': 'Marketing Automation'
    },
    'activecampaign': {
        'patterns': [r'actid\s*=\s*[\'"]?\d+', r'trackcmp_email', r'ActiveCampaign'],
        'urls': ['trackcmp.net', 'trackcmp2.com'],
        'category': 'Marketing Automation'
    },
    'klaviyo': {
        'patterns': [r'_learnq\.push', r'klaviyo\.init', r'klaviyo\.identify'],
        'urls': ['static.klaviyo.com', 'a.]klaviyo.com'],
        'category': 'Marketing Automation'
    },
    'mailchimp': {
        'patterns': [r'mc-embedded-subscribe', r'list-manage\.com'],
        'urls': ['chimpstatic.com', 'list-manage.com'],
        'category': 'Marketing Automation'
    },
    'braze': {
        'patterns': [r'braze\.initialize', r'appboy\.initialize', r'appboycdn'],
        'urls': ['js.appboycdn.com', 'sdk.iad-01.braze.com'],
        'category': 'Marketing Automation'
    },
    'customer_io': {
        'patterns': [r'_cio\.identify', r'customerioforms'],
        'urls': ['assets.customer.io', 'track.customer.io'],
        'category': 'Marketing Automation'
    },
    'iterable': {
        'patterns': [r'iterableTracker', r'_iaq\.push'],
        'urls': ['js.iterable.com'],
        'category': 'Marketing Automation'
    },
    'sendgrid': {
        'patterns': [r'sendgrid'],
        'urls': ['mc.sendgrid.com'],
        'category': 'Marketing Automation'
    },

    # Customer Support
    'intercom': {
        'patterns': [r'Intercom\([\'"]boot[\'"]', r'app_id:\s*[\'"]([a-z0-9]+)[\'"]'],
        'urls': ['widget.intercom.io'],
        'category': 'Customer Support'
    },
    'drift': {
        'patterns': [r'drift\.load\([\'"]([a-z0-9]+)[\'"]'],
        'urls': ['js.driftt.com'],
        'category': 'Customer Support'
    },
    'zendesk': {
        'patterns': [r'zE\(function\(\)'],
        'urls': ['static.zdassets.com'],
        'category': 'Customer Support'
    },
    'freshdesk': {
        'patterns': [r'FreshworksWidget', r'fw-widget'],
        'urls': ['widget.freshworks.com', 'euc-widget.freshworks.com'],
        'category': 'Customer Support'
    },
    'livechat': {
        'patterns': [r'__lc\.license\s*=\s*(\d+)', r'LiveChatWidget'],
        'urls': ['cdn.livechatinc.com'],
        'category': 'Customer Support'
    },
    'hubspot_conversations': {
        'patterns': [r'HubSpotConversations'],
        'urls': ['js.usemessages.com'],
        'owned_domains': ['hubspot.com', 'usemessages.com'],
        'category': 'Customer Support'
    },

    # CRM Tracking
    'salesforce_web_to_lead': {
        'patterns': [r'oid.*00D[A-Za-z0-9]{12,}', r'web-to-lead'],
        'urls': ['webto.salesforce.com'],
        'category': 'CRM'
    },

    # Other
    'microsoft_clarity': {
        'patterns': [r'clarity\([\'"]start[\'"]'],
        'urls': ['www.clarity.ms'],
        'owned_domains': ['clarity.ms'],
        'category': 'Analytics'
    },
    'bing_ads': {
        'patterns': [r'UET_TAG_ID'],
        'urls': ['bat.bing.com'],
        'owned_domains': ['bing.com', 'msn.com'],
        'category': 'Advertising'
    },
    'yandex_metrica': {
        'patterns': [r'ym\(\d+'],
        'urls': ['mc.yandex.ru/metrika'],
        'category': 'Analytics'
    },

    # Programmatic Advertising
    'liveramp': {
        'patterns': [r'idsync\.rlcdn\.com'],
        'urls': ['idsync.rlcdn.com'],
        'owned_domains': ['rlcdn.com', 'liveramp.com', 'pippio.com'],
        'category': 'Programmatic-Advertising'
    },
    'index_exchange': {
        'patterns': [r'casalemedia\.com'],
        'urls': ['dsum-sec.casalemedia.com'],
        'owned_domains': ['casalemedia.com', 'indexexchange.com'],
        'category': 'Programmatic-Advertising'
    },
    'pubmatic': {
        'patterns': [r'pubmatic\.com'],
        'urls': ['image2.pubmatic.com'],
        'owned_domains': ['pubmatic.com'],
        'category': 'Programmatic-Advertising'
    },
    'magnite': {
        'patterns': [r'rubiconproject\.com'],
        'urls': ['pixel.rubiconproject.com'],
        'owned_domains': ['rubiconproject.com', 'magnite.com'],
        'category': 'Programmatic-Advertising'
    },
}

# Common GA4 events to identify in dataLayer
GA4_EVENTS = {
    'page_view': 'Page View',
    'scroll': 'Scroll Tracking',
    'click': 'Click Tracking',
    'view_item': 'Product View',
    'add_to_cart': 'Add to Cart',
    'remove_from_cart': 'Remove from Cart',
    'view_cart': 'View Cart',
    'begin_checkout': 'Begin Checkout',
    'add_payment_info': 'Payment Info Added',
    'add_shipping_info': 'Shipping Info Added',
    'purchase': 'Purchase',
    'refund': 'Refund',
    'view_item_list': 'Product List View',
    'select_item': 'Product Click',
    'view_promotion': 'Promotion View',
    'select_promotion': 'Promotion Click',
    'login': 'Login',
    'sign_up': 'Sign Up',
    'share': 'Share',
    'search': 'Search',
    'generate_lead': 'Lead Generation',
    'view_search_results': 'Search Results View',
    'file_download': 'File Download',
    'form_start': 'Form Start',
    'form_submit': 'Form Submit'
}

# Technology detection patterns (built-in, no external dependencies)
TECHNOLOGY_PATTERNS = {

    # --- CMS Platforms ---
    'wordpress': {
        'patterns': [r'wp-content/', r'wp-includes/', r'wp-embed\.min\.js'],
        'meta': [('generator', r'WordPress')],
        'category': 'CMS'
    },
    'drupal': {
        'patterns': [r'Drupal\.settings', r'/sites/default/files/', r'/misc/drupal\.js'],
        'meta': [('generator', r'Drupal')],
        'category': 'CMS'
    },
    'joomla': {
        'patterns': [r'/media/jui/', r'/components/com_', r'Joomla!'],
        'meta': [('generator', r'Joomla')],
        'category': 'CMS'
    },
    'wix': {
        'patterns': [r'static\.parastorage\.com', r'wixBiSession', r'wix\.com/website-builder'],
        'meta': [('generator', r'Wix\.com')],
        'category': 'CMS'
    },
    'squarespace': {
        'patterns': [r'static\d?\.squarespace\.com', r'squarespace\.com/universal/'],
        'meta': [('generator', r'Squarespace')],
        'category': 'CMS'
    },
    'webflow': {
        'patterns': [r'data-wf-site', r'assets\.website-files\.com'],
        'meta': [('generator', r'Webflow')],
        'category': 'CMS'
    },
    'ghost': {
        'patterns': [r'ghost-(?:url|version)', r'/ghost/api/'],
        'meta': [('generator', r'Ghost')],
        'category': 'CMS'
    },
    'contentful': {
        'patterns': [r'contentful\.com', r'ctfassets\.net'],
        'meta': [],
        'category': 'Headless CMS'
    },
    'hubspot_cms': {
        'patterns': [r'hs-sites\.com', r'cdn2\.hubspot\.net/hub/'],
        'meta': [('generator', r'HubSpot')],
        'owned_domains': ['hubspot.com', 'hubspot.net', 'hs-sites.com', 'hsappstatic.net', 'hubspotusercontent-na1.net'],
        'category': 'CMS'
    },

    # --- E-commerce ---
    'shopify': {
        'patterns': [r'cdn\.shopify\.com', r'Shopify\.theme', r'sdks\.shopifycdn\.com'],
        'urls': ['cdn.shopify.com', 'sdks.shopifycdn.com'],
        'owned_domains': ['shopify.com', 'shopifycdn.com'],
        'meta': [('shopify-checkout-api-token', r'.')],
        'category': 'E-commerce'
    },
    'woocommerce': {
        'patterns': [r'wc-cart-fragments', r'class=["\']woocommerce', r'wp-content/plugins/woocommerce'],
        'meta': [('generator', r'WooCommerce')],
        'category': 'E-commerce'
    },
    'magento': {
        'patterns': [r'Magento_Ui', r'mage/cookies', r'/skin/frontend/.*Magento'],
        'meta': [],
        'category': 'E-commerce'
    },
    'bigcommerce': {
        'patterns': [r'cdn\d+\.bigcommerce\.com', r'bigcommerce\.com/s-'],
        'meta': [],
        'category': 'E-commerce'
    },
    'prestashop': {
        'patterns': [r'prestashop', r'/modules/ps_'],
        'meta': [('generator', r'PrestaShop')],
        'category': 'E-commerce'
    },

    # --- JavaScript Frameworks ---
    'react': {
        'patterns': [r'React\.createElement', r'__REACT', r'react-root', r'_reactRootContainer'],
        'meta': [],
        'category': 'JavaScript Framework'
    },
    'vue': {
        'patterns': [r'Vue\.js', r'__VUE__', r'data-v-[a-f0-9]'],
        'meta': [],
        'category': 'JavaScript Framework'
    },
    'angular': {
        'patterns': [r'ng-version=', r'ng-app', r'angular\.min\.js'],
        'meta': [],
        'category': 'JavaScript Framework'
    },
    'svelte': {
        'patterns': [r'__svelte', r'svelte-[a-z0-9]', r'svelte\.dev'],
        'meta': [],
        'category': 'JavaScript Framework'
    },
    'next_js': {
        'patterns': [r'__NEXT_DATA__', r'_next/static', r'_next/image'],
        'meta': [],
        'category': 'JavaScript Framework'
    },
    'nuxt': {
        'patterns': [r'__NUXT__', r'_nuxt/', r'nuxt\.js'],
        'meta': [],
        'category': 'JavaScript Framework'
    },
    'gatsby': {
        'patterns': [r'___gatsby', r'gatsby-'],
        'meta': [('generator', r'Gatsby')],
        'category': 'JavaScript Framework'
    },
    'ember': {
        'patterns': [r'ember\.js', r'ember-cli', r'data-ember-action'],
        'meta': [],
        'category': 'JavaScript Framework'
    },
    'astro': {
        'patterns': [r'astro-island', r'astro-slot'],
        'meta': [('generator', r'Astro')],
        'category': 'JavaScript Framework'
    },

    # --- JavaScript Libraries ---
    'jquery': {
        'patterns': [r'jquery[\.-][\d\.]+\.(?:min\.)?js', r'jQuery\s*v?\d'],
        'meta': [],
        'category': 'JavaScript Library'
    },
    'lodash': {
        'patterns': [r'lodash\.min\.js', r'lodash\.core\.js'],
        'meta': [],
        'category': 'JavaScript Library'
    },
    'axios': {
        'patterns': [r'axios\.min\.js', r'axios/dist/'],
        'meta': [],
        'category': 'JavaScript Library'
    },
    'gsap': {
        'patterns': [r'gsap\.min\.js', r'greensock', r'TweenMax'],
        'meta': [],
        'category': 'JavaScript Library'
    },

    # --- CSS / UI Frameworks ---
    'bootstrap': {
        'patterns': [r'bootstrap[\.-][\d\.]+\.(?:min\.)?(?:css|js)'],
        'meta': [],
        'category': 'CSS Framework'
    },
    'tailwindcss': {
        'patterns': [r'tailwindcss', r'tailwind\.min\.css'],
        'detection_note': 'unreliable: purged/bundled Tailwind is not detectable from filename alone',
        'meta': [],
        'category': 'CSS Framework'
    },
    'material_ui': {
        'patterns': [r'MuiButton', r'Mui[A-Z]', r'@mui/material'],
        'meta': [],
        'category': 'CSS Framework'
    },
    'font_awesome': {
        'patterns': [r'font-awesome', r'fontawesome', r'fa-[a-z]+-[a-z]+'],
        'meta': [],
        'owned_domains': ['fontawesome.com'],
        'category': 'UI Library'
    },

    # --- CDN / Infrastructure ---
    'cloudflare': {
        'patterns': [r'cdnjs\.cloudflare\.com', r'cloudflareinsights\.com'],
        'headers': [('server', r'cloudflare')],
        'owned_domains': ['cloudflare.com', 'cloudflareinsights.com'],
        'category': 'CDN'
    },
    'akamai': {
        'patterns': [r'akamai\.net', r'akamaized\.net'],
        'headers': [('server', r'AkamaiGHost')],
        'category': 'CDN'
    },
    'fastly': {
        'patterns': [r'fastly\.net', r'fastly-insights'],
        'headers': [('via', r'varnish'), ('x-served-by', r'cache-')],
        'category': 'CDN'
    },
    'amazon_cloudfront': {
        'patterns': [r'cloudfront\.net'],
        'headers': [('via', r'CloudFront'), ('x-amz-cf-id', r'.')],
        'category': 'CDN'
    },
    'vercel': {
        'patterns': [r'vercel\.app', r'vercel-insights'],
        'headers': [('x-vercel-id', r'.'), ('server', r'Vercel')],
        'category': 'Hosting'
    },
    'netlify': {
        'patterns': [r'netlify\.app', r'netlify-identity'],
        'headers': [('server', r'Netlify'), ('x-nf-request-id', r'.')],
        'category': 'Hosting'
    },

    # --- Web Servers ---
    'nginx': {
        'patterns': [],
        'headers': [('server', r'nginx')],
        'category': 'Web Server'
    },
    'apache': {
        'patterns': [],
        'headers': [('server', r'Apache')],
        'category': 'Web Server'
    },

    # --- Programming Languages / Runtimes ---
    'php': {
        'patterns': [],
        'headers': [('x-powered-by', r'PHP'), ('server', r'PHP')],
        'category': 'Programming Language'
    },
    'asp_net': {
        'patterns': [r'__VIEWSTATE', r'__EVENTVALIDATION'],
        'headers': [('x-powered-by', r'ASP\.NET'), ('x-aspnet-version', r'.')],
        'category': 'Programming Language'
    },

    # --- Payment / E-commerce Services ---
    'stripe': {
        'patterns': [r'js\.stripe\.com', r'Stripe\(', r'stripe-js'],
        'meta': [],
        'category': 'Payment'
    },
    'paypal': {
        'patterns': [r'paypal\.com/sdk', r'paypalobjects\.com'],
        'meta': [],
        'category': 'Payment'
    },

    # --- Performance / Monitoring ---
    'new_relic': {
        'patterns': [r'newrelic', r'NREUM', r'nr-data\.net'],
        'meta': [],
        'category': 'Performance Monitoring'
    },
    'datadog': {
        'patterns': [r'datadoghq\.com', r'dd-rum', r'DD_RUM'],
        'meta': [],
        'category': 'Performance Monitoring'
    },
    'sentry': {
        'patterns': [r'sentry\.io', r'Sentry\.init', r'@sentry/browser'],
        'meta': [],
        'category': 'Error Tracking'
    },

    # --- Fonts / Typography ---
    'google_fonts': {
        'patterns': [r'fonts\.googleapis\.com', r'fonts\.gstatic\.com'],
        'meta': [],
        'owned_domains': ['googleapis.com', 'gstatic.com'],
        'category': 'Font Service'
    },
    'typekit': {
        'patterns': [r'use\.typekit\.net', r'use\.typekit\.com'],
        'meta': [],
        'category': 'Font Service'
    },

    # --- Security ---
    'recaptcha': {
        'patterns': [r'google\.com/recaptcha', r'grecaptcha', r'recaptcha/api'],
        'meta': [],
        'owned_domains': ['google.com', 'gstatic.com'],
        'category': 'Security'
    },
    'hcaptcha': {
        'patterns': [r'hcaptcha\.com', r'h-captcha'],
        'meta': [],
        'category': 'Security'
    },
}
