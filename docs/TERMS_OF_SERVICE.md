# Terms of Service — cryptodivlinbot

_Last updated: 2026-04-26_

By interacting with the **cryptodivlinbot** Telegram bot you agree to
the following terms. The bot is open-source software available at
<https://github.com/ZaGOR-1/cryptodivlinbot>; deployed instances are
operated by individual third parties.

## 1. What this bot does

cryptodivlinbot tracks the top-N cryptocurrencies by market cap and
sends you:

- A **periodic digest** of current prices and 24-hour percentage moves.
- **Spike alerts** when a tracked coin moves more than the configured
  percentage threshold within the configured time window.

You control your subscription with `/subscribe` and `/unsubscribe` and
your alert sensitivity with `/setthreshold`.

## 2. Not financial advice

**The information the bot delivers is for informational purposes
only.** It is not, and must not be relied on as, financial, investment,
trading, tax, or legal advice. Cryptocurrency markets are volatile and
you can lose your entire investment. Always do your own research and,
if needed, consult a licensed financial advisor before making any
trading decision.

The operator and the contributors to the source code make **no
warranty** as to the accuracy, completeness, freshness, or fitness for
any particular purpose of the data delivered by the bot. The
underlying market-data providers (CoinGecko, Binance) may report
inaccurate, delayed, or missing prices.

## 3. Acceptable use

You may not:

- Use the bot to attempt to manipulate, mislead, or defraud others.
- Reverse-engineer or attack the bot's infrastructure beyond what is
  permitted by the published source license (MIT-style — see the
  repository LICENSE file if present, otherwise the deployer's terms).
- Spam the bot with abusive request volumes designed to disrupt
  service for others.

The operator may rate-limit or stop responding to chats that
demonstrably violate this section.

## 4. Privacy

How the bot handles your data is described in the [Privacy
Policy](./PRIVACY_POLICY.md). In short: the bot stores only your chat
id, language preference, alert threshold, subscription status, and
short-lived cooldown timestamps. You can request full deletion at any
time via `/forgetme`.

## 5. Availability and changes

The bot is provided **as-is** and on a **best-effort** basis. The
operator may take it offline, change features, or stop running it
entirely at any time without notice. The source code may be updated;
see the GitHub repository for the change log.

## 6. Liability

To the maximum extent permitted by applicable law, the operator,
contributors, and source-code authors are **not liable** for any
direct, indirect, incidental, consequential, special, exemplary, or
punitive damages — including but not limited to loss of profits,
trading losses, data loss, or business interruption — arising out of
or in connection with the use of, or inability to use, the bot.

## 7. Third-party data sources

Market data is fetched from CoinGecko (primary) and Binance (fallback)
public APIs. Use of those APIs is subject to their own terms; the
operator does not control them.

## 8. Governing law and disputes

These terms are governed by the laws of the operator's country of
residence. Any disputes that cannot be resolved amicably should first
be raised via GitHub Issues at
<https://github.com/ZaGOR-1/cryptodivlinbot/issues>.

## 9. Changes to these terms

If these terms change materially, the operator will note it in the
GitHub repository's `CHANGELOG.md` and update the "Last updated" date
above. Continued use of the bot after the update constitutes
acceptance.

## 10. Contact

For questions about these terms, contact the bot operator via the
Telegram chat with the bot, or open an issue on the public repository.
