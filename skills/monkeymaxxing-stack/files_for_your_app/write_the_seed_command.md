# How to write the app's seed command

Developers need data to work with. On a laptop and on `staging01`, that
data comes from the app's seed command, which fills an empty database with
invented records. Seed data never comes from a copy of production. The
requirement is checklist item `<app>_seed_command_fills_test_data`, and
chapter 2 (get your app ready to deploy) gives the reasons. This page says how to build
the seed command for any app. The coding agent writes the seed command in
the app's repository, as a change the person reviews.

## What the seed command must do

- **Fill an empty database with invented records** after the app's
  migrations. The records let a developer try each of the app's main
  workflows.
- **Run only when `APP_ENV` is `development` or `staging`.** With any other
  value, or none, the seed command stops before it touches the database:
  `seed-test-data refuses to run: APP_ENV must be development or staging, so production never gets test data`.
- **Leave existing test records unchanged when run again.** Give each
  fixed record a fixed unique value, such as an email. Insert with
  `ON CONFLICT DO NOTHING`, or skip a record that already exists.
- **Take one size option for generating many records.** Many records show
  problems such as a slow query.

## How to build the seed command

1. **Start from the app's existing seed code.** Many apps already have a
   seed file, and most frameworks have a seed tool built in (see
   [Seed tools by framework](#seed-tools-by-framework)). Extend the
   existing seed code rather than adding a second one.

   Some framework seed commands cannot take the size option: Laravel's
   `php artisan db:seed` accepts only its own options. Then add an app
   command that calls the same seed code and takes the size option. The
   Stack's Laravel example has `php artisan portal:seed-test-data`. Some
   tools pass extra options only after `--`, as
   `npx prisma db seed -- --orders 50000` does. Write the complete command
   in the app's README.
2. **Read the schema and the app's models.** List the tables, their
   foreign keys, and their unique columns. List the states each record can
   be in, such as an order that is open, paid, or refunded. Fill parent
   tables before child tables.
3. **Write a small fixed set first.** Create one record for each state a
   user can see. Use fixed values, so tests and bug reports can name the
   records. Create the fixed set with the app's own code for creating
   records, so the app's rules and default values apply. Some frameworks
   do not validate on save, such as Django: call the validation the app
   relies on, such as Django's `full_clean()`.

   When the app has sign-in, include one test identity that signs in the
   app's usual way. For password sign-in, the password comes from a
   setting, such as `FIXTURE_PASSWORD`, never from the code.
4. **Name the size option after the app's main record,** the record that
   grows with the business, such as `--orders 1000000` or `--shops 5000`.
   Generate the related records that the main record needs, such as a
   customer for each order. For large sizes, prefer bulk inserts, one SQL
   statement for each table, over one call to the app's code for each row.
   Fill any column that the app's code would normally calculate. Compute
   any password hash once and give every generated account the same hash.
5. **Make generated data repeatable.** Build each generated value from its
   row number, as the example below does. A fake-data library instead
   needs a fixed random seed, the starting value of its random numbers.
   It also needs a fixed reference date for dates such as "last week",
   and the app's pinned library version. Name generated records by a
   stable value, not by database id: "open the order of
   `customer-0000031@example.com`". Database ids can differ between two
   laptops.
6. **Keep values obviously invented.** Use emails at `example.com`. Use
   phone numbers set aside for fiction, such as 555-0100 to 555-0199 in
   the US. Generate names and addresses from the row number or with a
   fake-data library. Never copy a value from production, even a single
   customer's name.
7. **Add a test that runs the seed command on every build.** The test:
   - creates an empty test database and runs the migrations;
   - runs the seed command twice, without clearing the database between
     the two runs, and checks the record counts and the fixed set's values;
   - runs the size option with a small number, such as 20, and checks the
     generated records;
   - checks that `APP_ENV=production`, and an unset `APP_ENV`, refuse and
     change no records.

   The app's tests run before every image build, in CI when the team uses
   CI, otherwise on the laptop. With small numbers, the test adds seconds
   to the build. Never run a large size in the tests.

Reason for step 7: a seed command that nobody runs breaks at the next
migration, and nobody notices. Developers then go back to copying
production, which the seed command exists to prevent.

## When a bug needs particular records

A bug report says "the invoice page fails for a shop with no products".
Add a shop with no products to the fixed set or to the test's setup. Add a
test that opens the invoice page of that shop. The test keeps the bug from
coming back. Never copy the customer's rows to reproduce a bug.

Reading how many rows production holds is fine, and helps choose realistic
sizes. A count holds no personal data. Never copy the rows themselves:

```sql
-- Run read-only on a production server. Copy only the numbers.
SELECT relname AS table_name, n_live_tup AS approximate_rows
FROM pg_stat_user_tables ORDER BY n_live_tup DESC;
```

## A worked example: a small shop

The shop app has `shops`, `products`, `customers`, and `orders`. An order
belongs to a customer and has a status: `open`, `paid`, or `refunded`.

The fixed set, created with the app's own code:

| Record | Purpose of the record |
| --- | --- |
| Shop `Example Garden Shop`, owner `owner@example.com` | The account the developer signs in with |
| Shop `Example Empty Shop`, with no products | The empty states of every page |
| Three products in the garden shop, one out of stock | Product lists, and the out-of-stock label |
| Customer `customer@example.com` | Orders need a customer |
| Three orders: one `open`, one `paid`, one `refunded` | Every order state a user can see |

The size option, `--orders N`, adds generated customers and orders to the
garden shop with plain SQL. Every value comes from the row number `n`, so
the same `N` gives the same rows. `$1` is `N`, and `$2` is the garden
shop's id:

```sql
INSERT INTO customers (email, name)
SELECT 'customer-' || lpad(n::text, greatest(7, length(n::text)), '0') || '@example.com',
       'Test Customer ' || n
FROM generate_series(1, $1) AS n
ON CONFLICT (email) DO NOTHING;

INSERT INTO orders (customer_id, shop_id, status, total_cents, created_at)
SELECT c.id, $2,
       (ARRAY['open', 'paid', 'refunded'])[1 + n % 3],
       100 + (n * 37) % 20000,
       timestamp '2026-01-01' + n * interval '1 minute'
FROM generate_series(1, $1) AS n
JOIN customers c
  ON c.email = 'customer-' || lpad(n::text, greatest(7, length(n::text)), '0') || '@example.com'
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

Each generated customer gets one order. Running the seed command again
with the same `N` adds nothing. A larger `N` adds only the missing rows.
With 200,000 orders, the two statements took a few seconds.

For complete working seed commands, see the Stack repository's example
apps, in `examples/app-frameworks/` and `examples/app-platform-migrations/`.
Each example's `seed-test-data` command and its test follow this page.

## Seed tools by framework

The table names the usual place for the seed command in each framework.
For a framework not listed, look for the framework's own seed tool.
Otherwise, add a command to the app's command-line entry point.
Fake-data libraries are optional. Values built from the row number need no
fake-data library.

| Framework | Where the seed command goes | Usual fake-data library |
| --- | --- | --- |
| Rails | `db/seeds.rb`, run by `bin/rails db:seed` ([Rails guide](https://guides.rubyonrails.org/active_record_migrations.html#migrations-and-seed-data)). Read the size option from a setting, or add a Rake task that takes it. | Faker, often with factory_bot |
| Laravel | Seeders and model factories ([Laravel docs](https://laravel.com/docs/seeding)), with an Artisan command that takes the size option | Faker for PHP, built into Laravel's factories |
| Django | A management command, run by `python manage.py <name>` ([Django docs](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)). Django's fixtures, files of saved records, can hold only the fixed set. | Faker, often with factory_boy |
| FastAPI | A command in the app's command-line entry point, using the app's existing database code | Faker |
| Next.js with Prisma | Prisma's seed script, run by `npx prisma db seed` ([Prisma docs](https://www.prisma.io/docs/orm/prisma-migrate/workflows/seeding)), with the size option after `--` | `@faker-js/faker` |
| Express, Nuxt, SvelteKit, TanStack Start | A script in `package.json`, or the query library's seed feature: Knex seeds ([Knex docs](https://knexjs.org/guide/migrations.html)) or Drizzle's seed tool ([Drizzle docs](https://orm.drizzle.team/docs/seed-overview)) | `@faker-js/faker` |
| Go | A subcommand of the app's program, such as `app seed-test-data` | gofakeit |
| Rust | A subcommand of the app's program | the `fake` crate |

## Tools that copy production and mask it

Some tools copy production, or a part of it, and replace the personal data
with fake values. A copy made this way is called a sanitized copy, and the
Stack does not use sanitized copies. Such a tool needs a masking rule for
every column that holds personal data. A new column can be missed until
someone adds its rule. When the copy includes the missed column, customer
data leaves production without anyone noticing. Invented data has no such
gap. A team that still chooses such a tool records the choice as a
deviation in the checklist, with its reason.
