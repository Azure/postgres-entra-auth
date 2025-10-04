using Npgsql;

namespace GettingStarted;

// Console application to demonstrate using Entra authentication to connect to Azure PostgreSQL database for an extended period of time
class PersistentProgram : BaseDbConnectionProgram
{
    static async Task Main(string[] args)
    {
        await RunMain(args, RunDatabaseQueries);
    }

    static async Task RunDatabaseQueries(NpgsqlConnection connection)
    {
        Console.WriteLine("Running queries every 2 minutes for 16 minutes...");

        for (int i = 1; i <= 8; i++)
        {
            Console.WriteLine($"Execution #{i} at {DateTime.Now:HH:mm:ss}");

            // Run a simple query
            using var cmd = new NpgsqlCommand("SELECT version()", connection);
            var version = await cmd.ExecuteScalarAsync();
            Console.WriteLine($"Connected to PostgreSQL: {version}");

            if (i < 8)
            {
                await Task.Delay(TimeSpan.FromMinutes(2));
            }
        }

        Console.WriteLine("Completed all executions.");
    }
}