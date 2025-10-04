using Npgsql;

namespace GettingStarted;

// Console application to demonstrate using Entra authentication to connect to Azure PostgreSQL database for an indefinite period of time
// to test automatic token refresh functionality
class EverlastingProgram : BaseDbConnectionProgram
{
    static async Task Main(string[] args)
    {
        await RunMain(args, RunDatabaseQueries);
    }

    static async Task RunDatabaseQueries(NpgsqlConnection connection)
    {
        Console.WriteLine("Running queries indefinitely every 2 minutes...Press Ctrl+C to stop.");
        var i = 1;

        while (true)
        {
            Console.WriteLine($"Execution #{i} at {DateTime.Now:HH:mm:ss}");

            // Run a simple query
            using var cmd = new NpgsqlCommand("SELECT version()", connection);
            var version = await cmd.ExecuteScalarAsync();
            Console.WriteLine($"Connected to PostgreSQL: {version}");
            await Task.Delay(TimeSpan.FromMinutes(2));
            i++;
        }
    }
}