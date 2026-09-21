// Independent complete-tuple CPU oracle: raw AND/OR/popcount, no stored counts/index.
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

struct Hit { uint64_t id; uint32_t intersection, union_count; };
static_assert(sizeof(Hit) == 16);

std::vector<uint64_t> load(const std::filesystem::path& p) {
    const auto bytes = std::filesystem::file_size(p);
    if (bytes % 8 || bytes > (1ULL << 30)) throw std::runtime_error("invalid input size");
    std::vector<uint64_t> data(bytes / 8);
    std::ifstream f(p, std::ios::binary);
    if (!f.read(reinterpret_cast<char*>(data.data()), static_cast<std::streamsize>(bytes)))
        throw std::runtime_error("short input read");
    return data;
}

bool hit(uint32_t c, uint32_t u, uint32_t m, uint32_t n) {
    return uint64_t(n) * uint64_t(c) >= uint64_t(m) * uint64_t(u);
}

int main(int argc, char** argv) {
    try {
        if (argc != 8) throw std::runtime_error("usage: oracle db_dir query_dir D m n output.bin max_rows");
        const uint64_t endian = 1;
        if (*reinterpret_cast<const unsigned char*>(&endian) != 1) throw std::runtime_error("little endian required");
        const auto D = std::stoul(argv[3]), m0 = std::stoul(argv[4]), n0 = std::stoul(argv[5]);
        if ((D != 256 && D != 2048) || !m0 || m0 > n0 || n0 > 2147483647UL)
            throw std::runtime_error("invalid width/threshold");
        const auto m = uint32_t(m0), n = uint32_t(n0);
        if (!hit(7, 10, 7, 10) || hit(6, 11, 7, 10) ||
            !hit(2048, 2048, 2147483647, 2147483647) || hit(2047, 2048, 2147483647, 2147483647))
            throw std::runtime_error("uint64 threshold fixture failed");
        const auto required = (uint64_t(2147483647) * (uint64_t(2048) + uint64_t(2048)) +
                               uint64_t(2147483647) * 2 - 1) / (uint64_t(2147483647) * 2);
        if (required != 2048) throw std::runtime_error("promotion fixture failed");
        const std::filesystem::path db(argv[1]), qdir(argv[2]), dest(argv[6]);
        if (std::filesystem::exists(dest)) throw std::runtime_error("output exists; refusing replacement");
        const auto ids = load(db / "ids.u64"), fp = load(db / "fp.u64");
        const auto qids = load(qdir / "ids.u64"), q = load(qdir / "fp.u64");
        const auto W = D / 64;
        if (fp.size() != ids.size() * W || q.size() != qids.size() * W || ids.size() > std::stoul(argv[7]))
            throw std::runtime_error("shape mismatch");
        auto sorted = ids;
        std::sort(sorted.begin(), sorted.end());
        if (std::adjacent_find(sorted.begin(), sorted.end()) != sorted.end()) throw std::runtime_error("duplicate ID");
        std::ofstream out(dest, std::ios::binary);
        for (size_t qi = 0; qi < qids.size(); ++qi) {
            uint64_t any = 0;
            for (size_t w = 0; w < W; ++w) any |= q[qi * W + w];
            if (!any) throw std::runtime_error("zero query");
            std::vector<Hit> hits;
            for (size_t i = 0; i < ids.size(); ++i) {
                uint32_t c = 0, u = 0;
                for (size_t w = 0; w < W; ++w) {
                    c += uint32_t(__builtin_popcountll(fp[i * W + w] & q[qi * W + w]));
                    u += uint32_t(__builtin_popcountll(fp[i * W + w] | q[qi * W + w]));
                }
                if (hit(c, u, m, n)) hits.push_back({ids[i], c, u});
            }
            std::sort(hits.begin(), hits.end(), [](const Hit& a, const Hit& b) { return a.id < b.id; });
            const uint64_t header[2] = {qids[qi], uint64_t(hits.size())};
            out.write(reinterpret_cast<const char*>(header), sizeof(header));
            out.write(reinterpret_cast<const char*>(hits.data()), static_cast<std::streamsize>(hits.size() * sizeof(Hit)));
            if (!out) throw std::runtime_error("output failure");
        }
        out.close();
        if (!out) throw std::runtime_error("output close failure");
        std::cout << "complete_queries=" << qids.size() << " database_rows=" << ids.size() << "\n";
        return 0;
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
